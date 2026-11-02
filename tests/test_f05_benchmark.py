"""Synthetic F-05 benchmark contracts; never contact an inference provider."""
import io
import json
import socket
import subprocess
from urllib.error import HTTPError

import pytest

from scripts import f05_benchmark as benchmark
from app.agent.llm_client import ChatClient, ProviderError
from app.agent.tool_registry import MAX_ARGUMENT_BYTES, ToolRegistry


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('benchmark tests must use synthetic config and injected HTTP transport')

    monkeypatch.setattr(benchmark.Config, 'from_env', forbidden)
    monkeypatch.setattr(benchmark, 'ChatClient', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    # Isolated HTTP workers must never bypass the in-process socket guards.
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


def test_offline_report_exercises_real_orchestrator_and_separate_metrics(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('network/configuration must not be used offline')

    monkeypatch.setattr(benchmark.Config, 'from_env', forbidden)
    monkeypatch.setattr(benchmark, 'ChatClient', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    report = benchmark.run_benchmark()
    assert report['mode'] == 'offline_scripted'
    assert report['live_http_requests'] == 0
    assert report['scripted_requests'] > 0
    assert len(report['turns']) == 8
    assert report['planned_http_requests'] == 15
    assert report['selected_scenarios'] == [case.name for case in benchmark.SCENARIOS]
    assert report['skipped_scenarios'] == []
    assert set(report['metrics']) == {
        'end_to_end_ms', 'http_completion_reliability', 'correct_tool_choice',
        'grounded_answer_success', 'safe_fallback_behavior', 'final_json_compliance',
    }
    assert report['metrics']['correct_tool_choice']['rate'] == 1
    assert report['metrics']['grounded_answer_success']['rate'] == 1
    assert report['metrics']['final_json_compliance']['rate'] == 1
    assert report['metrics']['safe_fallback_behavior']['evaluated'] == 0
    assert report['turns'][-1]['scenario'] == 'follow_up_details'
    assert report['turns'][-1]['tools'] == ['get_product_details']


def test_no_network_without_separate_real_authorization(monkeypatch):
    monkeypatch.setattr(benchmark.Config, 'from_env', lambda: pytest.fail('read .env before approval'))
    with pytest.raises(benchmark.BenchmarkRefused, match='REAL_AUTHORIZATION_REQUIRED'):
        benchmark.run_benchmark(real=True)


def test_live_default_uses_deterministic_bounded_subset():
    config = benchmark.Config(api_key='synthetic-benchmark-secret')
    created = []

    def factory(case):
        client = benchmark.ScriptedClient(case.responses)
        created.append(client)
        return client

    report = benchmark.run_benchmark(real=True, authorized=True, config=config,
                                     client_factory=factory)
    assert report['selected_scenarios'] == list(benchmark.BOUNDED_SCENARIO_NAMES)
    assert report['planned_http_requests'] == 11
    assert report['live_http_requests'] == 11
    assert sum(client.calls for client in created) == 11
    assert report['stop_reason'] is None
    assert report['metrics']['http_completion_reliability']['evaluated'] == 11
    assert report['skipped_scenarios'] == ['availability', 'comparison']
    assert report['skipped_scenario_reasons'] == {
        'availability': 'not_selected', 'comparison': 'not_selected',
    }


def test_live_request_cap_is_twelve_total_across_turns():
    config = benchmark.Config(api_key='synthetic-benchmark-secret')
    created = []

    def factory(case):
        client = benchmark.ScriptedClient(case.responses)
        created.append(client)
        return client

    report = benchmark.run_benchmark(real=True, authorized=True, config=config,
                                     scenarios=benchmark.SCENARIOS,
                                     client_factory=factory)
    assert report['planned_http_requests'] == 15
    assert report['live_http_requests'] == 12
    assert sum(client.calls for client in created) == 12
    assert report['stop_reason'] == 'HTTP_REQUEST_CAP'
    assert report['metrics']['http_completion_reliability']['evaluated'] == 12
    assert report['turns'][6]['scenario'] == 'follow_up_catalog'
    assert report['turns'][6]['execution_status'] == 'interrupted'
    assert report['skipped_scenarios'] == ['follow_up_details']
    assert report['skipped_scenario_reasons'] == {'follow_up_details': 'HTTP_REQUEST_CAP'}


def test_live_bounded_subset_still_caps_extra_model_requests():
    def factory(case):
        responses = list(case.responses)
        if case.factual:
            extra = benchmark.tool_calls(('list_categories', {}))
            extra['tool_calls'][0]['id'] = 'fixture_extra'
            responses.insert(-1, extra)
        return benchmark.ScriptedClient(responses)

    report = benchmark.run_benchmark(real=True, authorized=True,
        config=benchmark.Config(api_key='synthetic-benchmark-secret'), client_factory=factory)
    assert report['planned_http_requests'] == 11
    assert report['live_http_requests'] == 12
    assert report['stop_reason'] == 'HTTP_REQUEST_CAP'
    assert report['selected_scenarios'] == list(benchmark.BOUNDED_SCENARIO_NAMES)
    assert report['turns'][-1]['scenario'] == 'follow_up_catalog'
    assert report['turns'][-1]['execution_status'] == 'interrupted'
    assert report['skipped_scenario_reasons'] == {
        'availability': 'not_selected', 'comparison': 'not_selected',
        'follow_up_details': 'HTTP_REQUEST_CAP',
    }


def test_explicit_scenario_selection_is_canonical_and_reported():
    report = benchmark.run_benchmark(scenario_names=['policy', 'budget'])
    assert report['selected_scenarios'] == ['budget', 'policy']
    assert report['planned_http_requests'] == 4
    assert report['skipped_scenario_reasons']['availability'] == 'not_selected'
    assert report['skipped_scenario_reasons']['combined'] == 'not_selected'
    assert report['skipped_scenarios'] == [
        'availability', 'comparison', 'combined', 'out_of_scope',
        'follow_up_catalog', 'follow_up_details',
    ]


def test_follow_up_selection_requires_preceding_catalog_context():
    with pytest.raises(benchmark.BenchmarkRefused, match='SCENARIO_PREREQUISITE_REQUIRED'):
        benchmark.run_benchmark(scenario_names=['follow_up_details'])
    report = benchmark.run_benchmark(scenario_names=['follow_up_details', 'follow_up_catalog'])
    assert report['selected_scenarios'] == ['follow_up_catalog', 'follow_up_details']
    assert [turn['scenario'] for turn in report['turns']] == report['selected_scenarios']
    assert report['metrics']['grounded_answer_success']['rate'] == 1


@pytest.mark.parametrize('cases', [
    benchmark.SCENARIOS[-1:], tuple(reversed(benchmark.SCENARIOS[-2:])),
])
def test_explicit_follow_up_cases_require_preceding_catalog(cases):
    with pytest.raises(benchmark.BenchmarkRefused, match='SCENARIO_PREREQUISITE_REQUIRED'):
        benchmark.run_benchmark(real=True, authorized=True, scenarios=cases)


@pytest.mark.parametrize('request_cap', [1, 12])
@pytest.mark.parametrize('fail_first', [False, True])
def test_live_cap_bounds_actual_http_transport_attempts(monkeypatch, request_cap, fail_first):
    config = benchmark.Config(api_key='synthetic-benchmark-secret')
    cases = iter(benchmark.SCENARIOS)
    attempts = []

    def mock_client(configuration):
        responses = iter(next(cases).responses)

        def opener(request, timeout):
            attempts.append(request)
            if fail_first and len(attempts) == 1:
                raise HTTPError(request.full_url, 503, 'fixture failure', {}, None)
            response = io.BytesIO(json.dumps({
                'model': configuration.model, 'usage': {'cost': 0},
                'choices': [{'message': next(responses), 'finish_reason': 'stop'}],
            }).encode('utf-8'))
            response.status = 200
            return response

        return ChatClient(configuration, opener=opener)

    monkeypatch.setattr(benchmark, 'ChatClient', mock_client)
    report = benchmark.run_benchmark(real=True, authorized=True, config=config,
                                     scenarios=benchmark.SCENARIOS, request_cap=request_cap)
    assert len(attempts) == report['live_http_requests'] == request_cap
    assert report['stop_reason'] == 'HTTP_REQUEST_CAP'
    requests = [request for turn in report['turns'] for request in turn['requests']]
    assert len(requests) == request_cap
    if fail_first:
        assert requests[0]['http_status'] == 503
        assert requests[0]['error_code'] == 'PROVIDER_UNAVAILABLE'
    executed = [turn['scenario'] for turn in report['turns']]
    assert report['selected_scenarios'] == [case.name for case in benchmark.SCENARIOS]
    assert report['skipped_scenarios'] == [
        name for name in report['selected_scenarios'] if name not in executed
    ]
    assert set(report['skipped_scenario_reasons'].values()) == {'HTTP_REQUEST_CAP'}


@pytest.mark.parametrize('names', [[], ['missing'], ['budget', 'budget'], [1]])
def test_invalid_scenario_selection_is_refused(names):
    with pytest.raises(benchmark.BenchmarkRefused, match='INVALID_SCENARIO_SELECTION'):
        benchmark.run_benchmark(scenario_names=names)


def test_ambiguous_scenario_selection_is_refused():
    with pytest.raises(benchmark.BenchmarkRefused, match='AMBIGUOUS_SCENARIO_SELECTION'):
        benchmark.run_benchmark(scenarios=benchmark.SCENARIOS,
                                scenario_names=benchmark.BOUNDED_SCENARIO_NAMES)


@pytest.mark.parametrize('name,arguments,code', [
    ('search_products', '{}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "limit": 999}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "price_min_cents": 60000, '
                        '"price_max_cents": 50000}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "query": "baixo"}', 'INVALID_ARGUMENT'),
    ('search_products', '{', 'INVALID_ARGUMENT'),
    ('get_product_details', '{}', 'INVALID_ARGUMENT'),
    ('get_product_details', '{"product_id": 0}', 'INVALID_ARGUMENT'),
    ('search_store_policies', '{"query": "PIX", "limit": 6}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "limit": true}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "price_max_cents": 1.5}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "price_min_cents": -1}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "limit": NaN}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "availability": "live"}', 'INVALID_ARGUMENT'),
    ('search_products', '{"query": "violão", "sql": "SELECT 1"}', 'INVALID_ARGUMENT'),
    ('search_products', '[]', 'INVALID_ARGUMENT'),
    ('search_products', {'query': 'violão'}, 'INVALID_ARGUMENT'),
    ('search_products', 'x' * (MAX_ARGUMENT_BYTES + 1), 'INVALID_ARGUMENT'),
    ('get_product_details', '{"product_id": true}', 'INVALID_ARGUMENT'),
    ('get_product_details', '{"product_id": "101"}', 'INVALID_ARGUMENT'),
    ('search_store_policies', '{"query": null}', 'INVALID_ARGUMENT'),
    ('list_categories', '{"query": "all"}', 'INVALID_ARGUMENT'),
    ('missing_tool', '{}', 'UNKNOWN_TOOL'),
])
def test_synthetic_registry_rejects_invalid_tool_arguments(name, arguments, code):
    result = benchmark.SyntheticRegistry().dispatch(name, arguments)
    assert result['ok'] is False
    assert result['error']['code'] == code
    assert ToolRegistry().dispatch(name, arguments)['error']['code'] == code
    assert 'data' not in result


@pytest.mark.parametrize('name,arguments,expected', [
    ('search_products', '{"query": "violão", "price_max_cents": 50000}',
     'Violão Sintético'),
    ('get_product_details', '{"product_id": 101}', 'Violão Sintético'),
    ('list_categories', '{}', 'Violões'),
    ('search_store_policies', '{"query": "PIX"}', 'Pagamento sintético'),
    ('search_products', '{"query": null, "price_max_cents": 50000, "limit": 2}',
     'Violão Sintético'),
    ('search_products', '{"category": "Violões", "availability": "any"}',
     'Violão Sintético'),
])
def test_synthetic_registry_accepts_valid_tool_arguments(name, arguments, expected):
    result = benchmark.SyntheticRegistry().dispatch(name, arguments)
    assert result['ok'] is True
    assert expected in json.dumps(result, ensure_ascii=False)
    assert result['meta']['source'] == 'synthetic_fixture'


def test_catalog_fixture_count_matches_its_products():
    result = benchmark.SyntheticRegistry().dispatch('search_products', '{"query": "violão"}')
    assert result['meta']['returned'] == len(result['data']['products'])


def test_invalid_tool_arguments_cannot_produce_successful_evidence():
    case = benchmark.Scenario(
        'invalid_arguments', 'Quais violões até R$ 500?', ('search_products',),
        (benchmark.tool_calls(('search_products', {})),
         benchmark.final('Não encontrei evidência.', [])),
    )
    report = benchmark.run_benchmark(scenarios=[case])
    turn = report['turns'][0]
    assert turn['tool_success'] is False
    assert turn['grounded_answer_success'] is False
    assert turn['error_code'] == 'TOOL_FAILURE'
    assert report['scripted_requests'] == 1


def test_cli_list_scenarios_is_offline_and_reports_estimates(capsys, monkeypatch):
    monkeypatch.setattr(benchmark.Config, 'from_env',
                        lambda: pytest.fail('must not read configuration'))
    assert benchmark.main(['--list-scenarios']) == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing['max_live_http_requests'] == 12
    assert [item['name'] for item in listing['scenarios']] == [
        case.name for case in benchmark.SCENARIOS
    ]
    assert sum(item['planned_requests'] for item in listing['scenarios']) == 15
    assert listing['bounded_scenarios'] == list(benchmark.BOUNDED_SCENARIO_NAMES)


def test_cli_selected_scenarios_are_reported(capsys):
    assert benchmark.main(['--scenarios', 'policy,budget']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['selected_scenarios'] == ['budget', 'policy']
    assert [turn['scenario'] for turn in report['turns']] == ['budget', 'policy']
    assert set(report['skipped_scenario_reasons'].values()) == {'not_selected'}


def test_cli_incomplete_follow_up_is_refused_without_network(capsys):
    assert benchmark.main(['--scenarios', 'follow_up_details']) == 2
    assert json.loads(capsys.readouterr().out) == {
        'error_code': 'SCENARIO_PREREQUISITE_REQUIRED',
    }


@pytest.mark.parametrize('code,status', [
    ('PROVIDER_RATE_LIMIT', 429), ('PROVIDER_AUTH', 401), ('PROVIDER_AUTH', 403),
    ('UNAUTHORIZED_RESPONSE_MODEL', 200), ('NONZERO_PROVIDER_COST', 200),
    ('INVALID_PROVIDER_COST', 200),
])
def test_live_stops_without_retry_on_rate_auth_or_nonfree(code, status):
    clients = []

    def factory(case):
        client = benchmark.ScriptedClient([ProviderError(code, status)])
        clients.append(client)
        return client

    report = benchmark.run_benchmark(real=True, authorized=True,
        config=benchmark.Config(api_key='synthetic-benchmark-secret'), client_factory=factory)
    assert report['live_http_requests'] == 1
    assert len(clients) == 1
    assert report['stop_reason'] == code
    assert report['metrics']['safe_fallback_behavior']['rate'] == 1


def test_http_success_final_json_and_grounding_are_independent():
    case = benchmark.SCENARIOS[0]
    invalid = {'role': 'assistant', 'content': 'not JSON'}
    bad_price = benchmark.final('O instrumento custa R$ 999,99.', ['search_products'])
    reports = []
    for last in (invalid, bad_price):
        reports.append(benchmark.run_benchmark(scenarios=[case], client_factory=lambda c: (
            benchmark.ScriptedClient([c.responses[0], last]))))
    for report in reports:
        assert report['metrics']['http_completion_reliability']['rate'] == 1
        assert report['metrics']['grounded_answer_success']['rate'] == 0
        assert report['metrics']['safe_fallback_behavior']['rate'] == 1
    assert reports[0]['metrics']['final_json_compliance']['rate'] == 0
    assert reports[1]['metrics']['final_json_compliance']['rate'] == 1


def test_wrong_tool_is_not_counted_as_grounded_task_success():
    case = benchmark.SCENARIOS[0]
    client = benchmark.ScriptedClient([
        benchmark.tool_calls(('list_categories', {})),
        benchmark.final('O catálogo local tem a categoria Violões.', ['list_categories']),
    ])
    report = benchmark.run_benchmark(scenarios=[case], client_factory=lambda c: client)
    assert report['metrics']['correct_tool_choice']['rate'] == 0
    assert report['metrics']['grounded_answer_success']['rate'] == 0
    assert report['metrics']['final_json_compliance']['rate'] == 1


def test_latency_includes_failure_and_aggregation_is_deterministic():
    values = iter([0, 0.1, 0.1, 0.8])
    cases = benchmark.SCENARIOS[:2]
    report = benchmark.run_benchmark(scenarios=cases, clock=lambda: next(values),
        client_factory=lambda c: benchmark.ScriptedClient([ProviderError('PROVIDER_UNAVAILABLE', 503)]))
    assert report['metrics']['end_to_end_ms'] == {'p50': 400.0, 'p95': 670.0, 'count': 2}
    assert report['metrics']['http_completion_reliability']['rate'] == 0
    assert report['metrics']['safe_fallback_behavior']['rate'] == 1


def test_sanitized_report_does_not_contain_questions_or_arbitrary_metadata():
    case = benchmark.SCENARIOS[0]
    client = benchmark.ScriptedClient(case.responses)
    report = benchmark.run_benchmark(scenarios=[case], client_factory=lambda c: client)
    encoded = json.dumps(report, ensure_ascii=False)
    assert case.question not in encoded
    for forbidden in ('Authorization', 'synthetic-benchmark-secret', 'api_key', 'messages', 'content', 'arguments'):
        assert forbidden not in encoded
    assert report['turns'][0]['requests'][0]['returned_model'] == benchmark.OFFLINE_MODEL


def test_cli_real_refusal_is_sanitized(capsys):
    assert benchmark.main(['--real']) == 2
    assert 'REAL_AUTHORIZATION_REQUIRED' in capsys.readouterr().out


def test_request_cap_rejects_oversized_budget():
    with pytest.raises(benchmark.BenchmarkRefused, match='INVALID_HTTP_REQUEST_CAP'):
        benchmark.run_benchmark(request_cap=13)


def test_budget_tool_choice_requires_the_budget_arguments():
    case = benchmark.SCENARIOS[0]
    client = benchmark.ScriptedClient([
        benchmark.tool_calls(('search_products', {'query': 'violão'})), case.responses[1],
    ])
    report = benchmark.run_benchmark(scenarios=[case], client_factory=lambda c: client)
    assert report['metrics']['correct_tool_choice']['rate'] == 0
    assert report['metrics']['grounded_answer_success']['rate'] == 0
    assert report['metrics']['http_completion_reliability']['rate'] == 1


def test_live_benchmark_requires_same_model_provider_failover_off():
    from dataclasses import replace
    config = replace(benchmark.Config(api_key='synthetic-benchmark-secret'), provider_failover=True)
    with pytest.raises(benchmark.BenchmarkRefused, match='BENCHMARK_REQUIRES_FAILOVER_OFF'):
        benchmark.run_benchmark(real=True, authorized=True, config=config,
                               client_factory=lambda c: pytest.fail('must refuse before request'))


def test_real_metadata_redacts_secret_echoes_and_untrusted_diagnostics():
    config = benchmark.Config(api_key='synthetic-benchmark-secret')

    class MaliciousMetadata(benchmark.ScriptedClient):
        def complete(self, messages, tools):
            result = super().complete(messages, tools)
            self.last_model = 'evil/' + config.api_key + ':free'
            self.last_latency_ms = 'prompt and secret body'
            self.last_http_status = '200 unsafe raw status'
            return result

    report = benchmark.run_benchmark(real=True, authorized=True, config=config,
        scenarios=benchmark.SCENARIOS[:1], client_factory=lambda c: MaliciousMetadata(c.responses))
    encoded = json.dumps(report)
    for forbidden in (config.api_key, 'unsafe raw status', 'prompt and secret body'):
        assert forbidden not in encoded
    assert all(request['returned_model'] is None for request in report['turns'][0]['requests'])


@pytest.mark.parametrize('message', [
    benchmark.final('Instrumento disponível.', []),
    benchmark.final('Olá!', ['search_products'], kind='greeting'),
    benchmark.final('Instrumento disponível.', ['search_products', 'search_products']),
])
def test_final_json_compliance_checks_required_sources_protocol(message):
    assert benchmark._valid_final(message) is False
