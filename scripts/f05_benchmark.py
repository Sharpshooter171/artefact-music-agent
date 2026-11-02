"""Synthetic F-05 protocol benchmark; offline by default, never a model-quality claim.

Real mode requires a separate owner authorization asserted by --authorize-real.
The shared counter counts each ChatClient call, including failures, across all
scenarios. It never retries or changes the model/allowlist/configuration file.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import re
from time import monotonic

from app.agent.config import Config
from app.agent.llm_client import ChatClient, ProviderError
from app.agent.orchestrator import FALLBACK, RATE_FALLBACK, Orchestrator, PROVIDER_CODES
from app.agent.tool_registry import TOOL_SCHEMAS, parse_and_validate_arguments

MAX_LIVE_HTTP_REQUESTS = 12
OFFLINE_MODEL = 'fixture/offline:free'
STOP_CODES = frozenset({
    'PROVIDER_RATE_LIMIT', 'PROVIDER_AUTH', 'UNAUTHORIZED_RESPONSE_MODEL',
    'NONZERO_PROVIDER_COST', 'INVALID_PROVIDER_COST', 'PROVIDER_REDIRECT', 'UNSAFE_RESPONSE',
})
_TOOL_NAMES = frozenset(tool['function']['name'] for tool in TOOL_SCHEMAS)
_SAFE_CODES = PROVIDER_CODES | STOP_CODES | frozenset({
    'HTTP_REQUEST_CAP', 'GROUNDING_FAILED', 'NO_EVIDENCE', 'TOOL_FAILURE',
    'PROVIDER_ERROR', 'BUDGET_EXCEEDED', 'INVALID_RESPONSE', 'INVALID_INPUT',
    'REQUEST_DEADLINE_EXCEEDED', 'TURN_DEADLINE_EXCEEDED',
})
_FIXTURE_SOURCE = 'synthetic_fixture'


class BenchmarkRefused(Exception):
    """Fixed diagnostic only; no supplied values or exception causes."""


@dataclass(frozen=True)
class Scenario:
    name: str
    question: str
    tools: tuple[str, ...]
    responses: tuple[dict, ...]
    required_text: tuple[str, ...] = ()
    factual: bool = True
    session: str | None = None
    required_arguments: tuple[tuple[str, dict], ...] = ()


def final(text, sources=(), kind='answer'):
    return {'role': 'assistant', 'content': json.dumps({
        'kind': kind, 'text': text, 'sources': list(sources),
    }, ensure_ascii=False)}


def tool_calls(*calls):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': f'fixture_{index}', 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(arguments, ensure_ascii=False),
        }} for index, (name, arguments) in enumerate(calls)
    ]}


_CATALOG_FIXTURE = {'ok': True, 'data': {'products': [{
    'product_id': 101, 'name': 'Violão Sintético', 'availability': 'available',
    'price': {'amount_cents': 42990, 'currency': 'BRL'},
}, {
    'product_id': 102, 'name': 'Violão Alternativo Sintético', 'availability': 'available',
    'price': {'amount_cents': 45990, 'currency': 'BRL'},
}]}, 'meta': {'snapshot_id': 'synthetic', 'source': _FIXTURE_SOURCE, 'returned': 2}}
_POLICY_FIXTURE = {'ok': True, 'data': {'matches': [{
    'section_id': '3', 'pages': [3], 'title': 'Pagamento sintético',
    'content': 'PIX: desconto de 5%, não cumulativo com promoções.',
}], 'cautions': []}, 'meta': {'source': _FIXTURE_SOURCE, 'returned': 1}}
_CATALOG_ANSWER = final('Violão Sintético por R$ 429,90 no catálogo local.', ['search_products'])


SCENARIOS = (
    Scenario('budget', 'Estou começando no violão. Quais opções até R$ 500?',
             ('search_products',), (tool_calls(('search_products', {
                 'query': 'violão', 'price_max_cents': 50000, 'availability': 'available'})),
                 _CATALOG_ANSWER), ('429,90',),
             required_arguments=(('search_products', {'price_max_cents': 50000, 'availability': 'available'}),)),
    Scenario('availability', 'Tem violão disponível?', ('search_products',),
             (tool_calls(('search_products', {'query': 'violão', 'availability': 'available'})),
              _CATALOG_ANSWER), ('429,90',)),
    Scenario('comparison', 'Quais violões disponíveis custam menos?', ('search_products',),
             (tool_calls(('search_products', {'query': 'violão'})),
              final('Violão Sintético por R$ 429,90 e Violão Alternativo Sintético por R$ 459,90 '
                    'no catálogo local.', ['search_products'])), ('429,90', '459,90')),
    Scenario('policy', 'Como funciona o desconto no PIX?', ('search_store_policies',),
             (tool_calls(('search_store_policies', {'query': 'desconto PIX'})),
              final('PIX tem 5% de desconto, sem acumular promoções (seção 3, página 3).',
                    ['search_store_policies'])), ('5%', 'sem acumular')),
    Scenario('combined', 'Tem violão e desconto no PIX?',
             ('search_products', 'search_store_policies'),
             (tool_calls(('search_products', {'query': 'violão'}),
                         ('search_store_policies', {'query': 'desconto PIX'})),
              final('Violão Sintético por R$ 429,90 no catálogo local. PIX tem 5% de desconto, '
                    'sem acumular promoções (seção 3, página 3).',
                    ['search_products', 'search_store_policies'])), ('429,90', '5%')),
    Scenario('out_of_scope', 'Pode me ensinar programação?', (),
             (final('Posso ajudar com instrumentos da loja.', kind='out_of_scope'),),
             factual=False),
    Scenario('follow_up_catalog', 'Quais violões vocês têm?', ('search_products',),
             (tool_calls(('search_products', {'query': 'violão'})), _CATALOG_ANSWER),
             ('429,90',), session='follow_up'),
    Scenario('follow_up_details', 'Quero os detalhes desse modelo.', ('get_product_details',),
             (tool_calls(('get_product_details', {'product_id': 101})),
              final('Violão Sintético por R$ 429,90 no catálogo local.', ['get_product_details'])),
             ('429,90',), session='follow_up'),
)

# Bounded live default: 11 scripted requests, below the 12-request TOTAL cap.
BOUNDED_SCENARIO_NAMES = (
    'budget', 'policy', 'combined', 'out_of_scope', 'follow_up_catalog', 'follow_up_details',
)
BOUNDED_SCENARIOS = tuple(case for case in SCENARIOS if case.name in BOUNDED_SCENARIO_NAMES)


def select_scenarios(names):
    """Select named scenarios in canonical order; reject unknown or duplicate names."""
    if (not isinstance(names, (list, tuple)) or not names
            or any(not isinstance(name, str) for name in names)
            or len(set(names)) != len(names)):
        raise BenchmarkRefused('INVALID_SCENARIO_SELECTION')
    requested = set(names)
    if any(name not in {case.name for case in SCENARIOS} for name in requested):
        raise BenchmarkRefused('INVALID_SCENARIO_SELECTION')
    return tuple(case for case in SCENARIOS if case.name in requested)


class SyntheticRegistry:
    """Valid fixed envelopes only; enforces the catalog/policy validation contract."""
    @property
    def schemas(self):
        return deepcopy(TOOL_SCHEMAS)

    def dispatch(self, name, arguments):
        _, code = parse_and_validate_arguments(name, arguments)
        if code is not None:
            return {'ok': False, 'error': {'code': code}, 'meta': {}}
        if name == 'search_products':
            result = _CATALOG_FIXTURE
        elif name == 'get_product_details':
            result = {'ok': True, 'data': {'product': _CATALOG_FIXTURE['data']['products'][0]},
                      'meta': {'source': _FIXTURE_SOURCE}}
        elif name == 'search_store_policies':
            result = _POLICY_FIXTURE
        elif name == 'list_categories':
            result = {'ok': True, 'data': {'categories': [{
                'category_id': 1, 'name': 'Violões', 'product_count': 1,
            }]}, 'meta': {'source': _FIXTURE_SOURCE}}
        else:
            result = {'ok': False, 'error': {'code': 'UNKNOWN_TOOL'}, 'meta': {}}
        return deepcopy(result)


class ScriptedClient:
    """Scripted assistant messages exercise host protocol, not real intent selection."""
    def __init__(self, responses):
        self.responses = list(deepcopy(responses))
        self.calls = 0
        self.last_http_status = None
        self.last_model = None
        self.last_error_code = None
        self.last_latency_ms = 0.0

    def complete(self, messages, tools):
        self.calls += 1
        self.last_error_code = None
        self.last_model = None
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            self.last_http_status = getattr(item, 'http_status', None)
            self.last_error_code = getattr(item, 'code', 'PROVIDER_ERROR')
            raise item
        self.last_http_status = 200
        self.last_model = OFFLINE_MODEL
        return deepcopy(item)


def _safe_model(value, secret=''):
    if not isinstance(value, str) or len(value) > 160 or (secret and secret in value):
        return None
    if value == 'openrouter/free' or re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._-]+:free', value):
        return value
    return None


def _code(value):
    return value if isinstance(value, str) and value in _SAFE_CODES else 'PROVIDER_ERROR'


def _number(value):
    return (round(value, 3) if type(value) in (int, float)
            and math.isfinite(value) and 0 <= value <= 1e9 else None)


def _valid_final(message):
    if not isinstance(message, dict) or message.get('tool_calls'):
        return False
    try:
        data = json.loads(message.get('content', ''))
        return (isinstance(data, dict) and set(data) == {'kind', 'text', 'sources'}
                and data['kind'] in {'answer', 'out_of_scope', 'greeting', 'clarification'}
                and isinstance(data['text'], str) and bool(data['text'].strip())
                and isinstance(data['sources'], list)
                and all(isinstance(name, str) and name in _TOOL_NAMES for name in data['sources'])
                and len(data['sources']) == len(set(data['sources']))
                and bool(data['sources']) == (data['kind'] == 'answer'))
    except (TypeError, ValueError, RecursionError):
        return False


class _ObservedClient:
    def __init__(self, client, budget, config=None):
        self.client = client
        self.budget = budget
        self.config = config
        self.requests = []
        self.final_compliant = False
        self.selected_calls = []

    def complete(self, messages, tools):
        return self._complete(messages, tools, None)

    def complete_with_deadline(self, messages, tools, deadline):
        return self._complete(messages, tools, deadline)

    def _complete(self, messages, tools, deadline):
        if self.budget['real']:
            if self.budget['used'] >= self.budget['cap']:
                self.budget['stop'] = 'HTTP_REQUEST_CAP'
                raise ProviderError('HTTP_REQUEST_CAP')
            self.budget['used'] += 1
        try:
            method = getattr(self.client, 'complete_with_deadline', None)
            message = method(messages, tools, deadline) if deadline is not None and callable(method) else (
                self.client.complete(messages, tools))
            for call in message.get('tool_calls') or []:
                try:
                    function = call['function']
                    self.selected_calls.append((function['name'], json.loads(function['arguments'])))
                except (KeyError, TypeError, ValueError, RecursionError):
                    self.selected_calls.append((None, None))
            if not message.get('tool_calls'):
                self.final_compliant = _valid_final(message)
            return message
        finally:
            status = getattr(self.client, 'last_http_status', None)
            status = status if type(status) is int and 100 <= status <= 599 else None
            raw_code = getattr(self.client, 'last_error_code', None)
            code = None if raw_code is None else _code(raw_code)
            secret = getattr(self.config, 'api_key', '')
            self.last_diagnostic = {
                'http_status': status,
                'returned_model': _safe_model(getattr(self.client, 'last_model', None), secret),
                'latency_ms': _number(getattr(self.client, 'last_latency_ms', None)),
                'error_code': code,
            }
            self.requests.append(self.last_diagnostic.copy())
            if self.budget['real'] and code in STOP_CODES:
                self.budget['stop'] = code


def _fraction(values):
    values = [value for value in values if value is not None]
    passed = sum(value is True for value in values)
    return {'passed': passed, 'evaluated': len(values),
            'rate': round(passed / len(values), 6) if values else None}


def _percentile(values, quantile):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    return round(values[lower] + (values[upper] - values[lower]) * (position - lower), 3)


def aggregate(turns):
    durations = [turn['end_to_end_ms'] for turn in turns]
    requests = [request for turn in turns for request in turn['requests']]
    return {
        'end_to_end_ms': {'p50': _percentile(durations, .5), 'p95': _percentile(durations, .95),
                          'count': len(durations)},
        'http_completion_reliability': _fraction([
            request['http_status'] == 200 and request['error_code'] not in {
                'REQUEST_DEADLINE_EXCEEDED', 'TURN_DEADLINE_EXCEEDED',
                'PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE'} for request in requests]),
        'correct_tool_choice': _fraction([turn['correct_tool_choice'] for turn in turns]),
        'grounded_answer_success': _fraction([turn['grounded_answer_success'] for turn in turns]),
        'safe_fallback_behavior': _fraction([turn['safe_fallback_behavior'] for turn in turns]),
        'final_json_compliance': _fraction([turn['final_json_compliance'] for turn in turns]),
    }


def run_benchmark(*, real=False, authorized=False, config=None, client_factory=None,
                  scenarios=None, scenario_names=None,
                  request_cap=MAX_LIVE_HTTP_REQUESTS, clock=monotonic):
    if type(request_cap) is not int or not 1 <= request_cap <= MAX_LIVE_HTTP_REQUESTS:
        raise BenchmarkRefused('INVALID_HTTP_REQUEST_CAP')
    if scenarios is not None and scenario_names is not None:
        raise BenchmarkRefused('AMBIGUOUS_SCENARIO_SELECTION')
    if real and not authorized:
        raise BenchmarkRefused('REAL_AUTHORIZATION_REQUIRED')
    if scenarios is None:
        if scenario_names is not None:
            selected_scenarios = select_scenarios(scenario_names)
        elif real:
            selected_scenarios = BOUNDED_SCENARIOS
        else:
            selected_scenarios = SCENARIOS
    else:
        selected_scenarios = tuple(scenarios)
    preceding_names = set()
    for case in selected_scenarios:
        if case.name == 'follow_up_details' and 'follow_up_catalog' not in preceding_names:
            raise BenchmarkRefused('SCENARIO_PREREQUISITE_REQUIRED')
        preceding_names.add(case.name)
    if real:
        config = config if config is not None else Config.from_env()
        if getattr(config, 'provider_failover', False):
            raise BenchmarkRefused('BENCHMARK_REQUIRES_FAILOVER_OFF')
    planned_requests = sum(len(case.responses) for case in selected_scenarios)
    budget = {'real': real, 'used': 0, 'cap': request_cap, 'stop': None}
    turns = []
    sessions = {}
    for case in selected_scenarios:
        if budget['stop'] is not None:
            break
        if real and budget['used'] >= request_cap:
            budget['stop'] = 'HTTP_REQUEST_CAP'
            break
        underlying = (client_factory(case) if client_factory else ChatClient(config) if real else
                      ScriptedClient(case.responses))
        client = _ObservedClient(underlying, budget, config)
        key = case.session or case.name
        if key not in sessions:
            sessions[key] = Orchestrator(client, SyntheticRegistry())
        agent = sessions[key]
        agent.client = client
        started = clock()
        answer = agent.reply(case.question)
        duration = round(max(0, clock() - started) * 1000, 3)
        tools = [event['tool'] for event in agent.last_trace
                 if isinstance(event, dict) and event.get('tool') in _TOOL_NAMES]
        correct = set(tools) == set(case.tools) and all(
            any(name == expected_name and isinstance(arguments, dict)
                and all(arguments.get(key) == value for key, value in expected.items())
                for name, arguments in client.selected_calls)
            for expected_name, expected in case.required_arguments)
        error = _code(agent.last_error_code) if agent.last_error_code else None
        fallback = answer in (FALLBACK, RATE_FALLBACK)
        turns.append({
            'scenario': case.name, 'end_to_end_ms': duration,
            'execution_status': ('interrupted' if budget['stop'] == 'HTTP_REQUEST_CAP'
                                 else 'completed'),
            'requests': client.requests, 'tools': tools,
            'tool_success': all(event.get('ok') is True for event in agent.last_trace),
            'error_code': error, 'correct_tool_choice': correct,
            'grounded_answer_success': (error is None and correct and not fallback
                and all(text in answer for text in case.required_text)) if case.factual else None,
            'safe_fallback_behavior': fallback if error is not None else None,
            'final_json_compliance': client.final_compliant,
        })
    selected_names = [case.name for case in selected_scenarios]
    executed_names = [turn['scenario'] for turn in turns]
    skip_reasons = {
        case.name: 'not_selected' for case in SCENARIOS if case.name not in selected_names
    }
    for name in selected_names:
        if name not in executed_names:
            skip_reasons[name] = budget['stop'] or 'not_executed'
    skipped_names = [case.name for case in SCENARIOS if case.name in skip_reasons]
    skipped_names += [name for name in selected_names
                      if name in skip_reasons and name not in skipped_names]
    return {
        'mode': 'live_synthetic' if real else 'offline_scripted',
        'evidence': 'synthetic fixture assertions; no real latency or model-quality conclusion' if not real else
                    'synthetic questions and fixture sources; task assertions require owner review',
        'live_http_requests': budget['used'],
        'scripted_requests': sum(len(turn['requests']) for turn in turns) if not real else 0,
        'http_request_cap': request_cap, 'stop_reason': budget['stop'],
        'planned_http_requests': planned_requests,
        'selected_scenarios': selected_names,
        'skipped_scenarios': skipped_names,
        'skipped_scenario_reasons': skip_reasons,
        'metrics': aggregate(turns), 'turns': turns,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='F-05 synthetic benchmark; offline by default.')
    parser.add_argument('--real', action='store_true', help='Use the configured approved model; consumes free requests.')
    parser.add_argument('--authorize-real', action='store_true',
                        help='Assert separate explicit owner authorization for this live run (12 requests total).')
    parser.add_argument('--scenarios',
                        help='Comma-separated scenario names; live mode defaults to the bounded 11-request subset.')
    parser.add_argument('--list-scenarios', action='store_true',
                        help='List fixture scenarios and request estimates without contacting a provider.')
    args = parser.parse_args(argv)
    if args.list_scenarios:
        bounded = {case.name for case in BOUNDED_SCENARIOS}
        print(json.dumps({
            'max_live_http_requests': MAX_LIVE_HTTP_REQUESTS,
            'scenarios': [{'name': case.name, 'planned_requests': len(case.responses),
                           'bounded_default': case.name in bounded} for case in SCENARIOS],
            'bounded_scenarios': list(BOUNDED_SCENARIO_NAMES),
        }, ensure_ascii=False, indent=2))
        return 0
    try:
        names = (None if args.scenarios is None
                 else [name.strip() for name in args.scenarios.split(',') if name.strip()])
        report = run_benchmark(real=args.real, authorized=args.authorize_real,
                               scenario_names=names)
    except BenchmarkRefused as error:
        print(json.dumps({'error_code': str(error)}))
        return 2
    except Exception:
        print(json.dumps({'error_code': 'BENCHMARK_FAILED'}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
