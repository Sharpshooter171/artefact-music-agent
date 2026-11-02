"""Actual isolated tools and safe diagnostic classification; no model requests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket
import sys

import pytest

from app.agent import cli, tool_registry
from app.agent.deadline import Deadline
from app.agent.orchestrator import FALLBACK, Orchestrator
from app.agent.tool_registry import ToolRegistry


@pytest.fixture(autouse=True)
def no_model_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('tool diagnostic tests must never contact a model')

    monkeypatch.setattr(cli, 'ChatClient', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


def call(arguments):
    return {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': 'diagnostic_fixture', 'type': 'function',
        'function': {'name': 'search_products', 'arguments': arguments},
    }]}


def final(text):
    return {'role': 'assistant', 'content': json.dumps({
        'kind': 'answer', 'text': text, 'sources': ['search_products'],
    })}


class Client:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        return deepcopy(self.responses.pop(0))


@pytest.mark.parametrize('arguments,missing_catalog,expected', [
    ('{', False, 'INVALID_ARGUMENT'),
    ('{"query":"violão","limit":true}', False, 'INVALID_ARGUMENT'),
    ('{"category":"Categoria Sintética Ausente"}', False, 'CATEGORY_NOT_FOUND'),
    ('{"query":"violão"}', True, 'CATALOG_UNAVAILABLE'),
])
def test_production_worker_failure_retains_safe_cause(catalog, monkeypatch, tmp_path,
                                                    arguments, missing_catalog, expected):
    if missing_catalog:
        monkeypatch.setenv('EMPORIO_CATALOG_DB', str(tmp_path / 'missing.sqlite'))
    client = Client(call(arguments))
    agent = Orchestrator(client)
    assert agent.reply('Pergunta sintética privada') == FALLBACK
    assert client.calls == 1  # Failure is never sent back to the LLM for repair.
    assert agent.last_error_code == 'TOOL_FAILURE'
    assert agent.last_trace == [{'tool': 'search_products', 'ok': False, 'error_code': expected}]
    assert agent.last_tool_diagnostics[0]['error_code'] == expected
    assert agent.last_tool_diagnostics[0]['duration_ms'] >= 0


def test_caller_relative_catalog_path_matches_direct_and_worker(catalog, monkeypatch):
    monkeypatch.chdir(catalog.db_path.parent)
    monkeypatch.setenv('EMPORIO_CATALOG_DB', catalog.db_path.name)
    registry = ToolRegistry()
    arguments = '{"category":"Violões","limit":2}'
    direct = registry.dispatch('search_products', arguments)
    assert direct['ok'] is True
    assert registry.dispatch_with_deadline('search_products', arguments, Deadline(3)) == direct


@pytest.mark.parametrize('fabricate', [False, True])
def test_correct_worker_arguments_preserve_grounding(catalog, fabricate):
    result = ToolRegistry().dispatch('search_products', '{"category":"Violões","limit":1}')
    product = result['data']['products'][0]
    cents = product['price']['amount_cents']
    text = f'No catálogo local: R$ {cents // 100},{cents % 100:02d}.'
    if fabricate:
        text = 'No catálogo local: R$ 123456,78.'
    client = Client(call('{"category":"Violões","limit":1}'), final(text))
    agent = Orchestrator(client)
    answer = agent.reply('Qual é o preço?')
    assert client.calls == 2
    assert agent.last_trace == [{'tool': 'search_products', 'ok': True, 'error_code': None}]
    if fabricate:
        assert answer == FALLBACK
        assert agent.last_error_code == 'GROUNDING_FAILED'
    else:
        assert answer == text
        assert agent.last_error_code is None


def worker_fixture(tmp_path, monkeypatch, body):
    script = tmp_path / 'tool_protocol_fixture.py'
    script.write_text('import os,sys\nsys.stdin.buffer.read()\n' + body, encoding='utf-8')
    monkeypatch.setattr(tool_registry, '_tool_worker_command',
                        lambda: [sys.executable, '-I', str(script)])


@pytest.mark.parametrize('body', [
    'sys.stdout.write("not JSON PRIVATE_BODY /private/path")',
    'sys.stdout.write(\'{}\\n{}\\n\')',
    'sys.stdout.write(\'{"ok":"yes"}\\n\')',
    'sys.stdout.write(\'{"ok":false,"error":[]}\\n\')',
    'sys.exit(7)',
])
def test_worker_protocol_failure_is_distinct_and_redacted(tmp_path, monkeypatch, capsys, body):
    worker_fixture(tmp_path, monkeypatch, body)
    result = ToolRegistry().dispatch_with_deadline('search_products', '{"query":"violão"}', Deadline(3))
    assert result['ok'] is False
    assert result['error']['code'] == 'WORKER_PROTOCOL_ERROR'
    agent = Orchestrator(Client(call('{"query":"violão"}')))
    assert agent.reply('PRIVATE_CUSTOMER') == FALLBACK
    assert agent.last_trace[0]['error_code'] == 'WORKER_PROTOCOL_ERROR'
    cli._print_debug(agent)
    output = capsys.readouterr().out
    assert 'WORKER_PROTOCOL_ERROR' in output
    for private in ('PRIVATE_BODY', '/private/path', str(tmp_path), 'PRIVATE_CUSTOMER', 'Traceback'):
        assert private not in output


@pytest.mark.parametrize('code', ['INVALID_ARGUMENT', 'CATEGORY_NOT_FOUND',
                                 'CATALOG_UNAVAILABLE', 'WORKER_PROTOCOL_ERROR', 'TOOL_FAILURE',
                                 'PRIVATE_SECRET /private/path', [], None])
def test_only_allowlisted_tool_error_codes_reach_debug(code, capsys):
    class UntrustedRegistry:
        schemas = ToolRegistry().schemas

        def dispatch(self, name, arguments):
            return {'ok': False, 'error': {'code': code, 'message': 'PRIVATE_BODY',
                    'details': {'arguments': 'PRIVATE_ARGUMENTS'}},
                    'meta': {'path': '/private/path', 'product': 'PRIVATE_PRODUCT'}}

    agent = Orchestrator(Client(call('{"query":"PRIVATE_QUERY"}')), UntrustedRegistry())
    assert agent.reply('PRIVATE_CUSTOMER') == FALLBACK
    expected = code if isinstance(code, str) and code in {
        'INVALID_ARGUMENT', 'CATEGORY_NOT_FOUND', 'CATALOG_UNAVAILABLE',
        'WORKER_PROTOCOL_ERROR', 'TOOL_FAILURE',
    } else 'TOOL_FAILURE'
    assert agent.last_trace[0]['error_code'] == expected
    assert agent.last_tool_diagnostics[0]['error_code'] == expected
    cli._print_debug(agent)
    output = capsys.readouterr().out
    assert expected in output
    diagnostics = json.dumps([agent.last_trace, agent.last_tool_diagnostics, agent.last_turn])
    for private in ('PRIVATE_BODY', 'PRIVATE_ARGUMENTS', 'PRIVATE_PRODUCT', 'PRIVATE_QUERY',
                    'PRIVATE_CUSTOMER', 'PRIVATE_SECRET', '/private/path'):
        assert private not in output + diagnostics


def test_unexpected_tool_exception_remains_generic_and_redacted(capsys):
    class BrokenRegistry:
        schemas = ToolRegistry().schemas

        def dispatch(self, name, arguments):
            raise RuntimeError('PRIVATE_SECRET /private/path PRIVATE_PRODUCT')

    agent = Orchestrator(Client(call('{"query":"violão"}')), BrokenRegistry())
    assert agent.reply('PRIVATE_CUSTOMER') == FALLBACK
    assert agent.last_trace[0]['error_code'] == 'TOOL_FAILURE'
    cli._print_debug(agent)
    output = capsys.readouterr().out
    assert 'PRIVATE_' not in output
    assert '/private/path' not in output


def test_worker_malformed_ipc_is_protocol_error_without_traceback(monkeypatch, tmp_path):
    from app.agent import tool_worker

    driver = tmp_path / 'malformed_ipc_fixture.py'
    worker_path = Path(tool_worker.__file__).resolve()
    driver.write_text(
        'import io,runpy,sys\n'
        'sys.stdin=io.TextIOWrapper(io.BytesIO(b"malformed PRIVATE_ARGUMENTS"))\n'
        f'runpy.run_path({str(worker_path)!r},run_name="__main__")\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(tool_registry, '_tool_worker_command',
                        lambda: [sys.executable, '-I', str(driver)])
    result = ToolRegistry().dispatch_with_deadline('list_categories', '{}', Deadline(3))
    assert result['error']['code'] == 'WORKER_PROTOCOL_ERROR'
    assert 'PRIVATE_ARGUMENTS' not in json.dumps(result)
