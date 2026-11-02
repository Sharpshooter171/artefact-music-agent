"""One HTTP request in an expendable interpreter; private, bounded pipe protocol.

This file is launched with Python -I, not imported as an application entry point.
The API key arrives on stdin. No raw errors or response bodies go to stderr.
"""
from __future__ import annotations

import base64
import json
import socket
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

MAX_RESPONSE_BYTES = 128 * 1024
MAX_REQUEST_BYTES = 256 * 1024
MAX_IPC_INPUT = 2 * MAX_REQUEST_BYTES + 8192
MAX_IPC_OUTPUT = 2 * MAX_RESPONSE_BYTES + 4096
ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'


class NoRedirect(HTTPRedirectHandler):
    """Never forward Authorization to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_error_code(status):
    if status == 429:
        return 'PROVIDER_RATE_LIMIT'
    if status in (401, 403):
        return 'PROVIDER_AUTH'
    if 300 <= status < 400:
        return 'PROVIDER_REDIRECT'
    if status >= 500:
        return 'PROVIDER_UNAVAILABLE'
    return 'PROVIDER_HTTP_ERROR'


def _emit(value):
    output = json.dumps(value, separators=(',', ':'), allow_nan=False).encode() + b'\n'
    if len(output) > MAX_IPC_OUTPUT:
        output = b'{"error_code":"WORKER_PROTOCOL_ERROR","http_status":null}\n'
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


def main():
    status = None
    try:
        raw_input = sys.stdin.buffer.read(MAX_IPC_INPUT + 1)
        if len(raw_input) > MAX_IPC_INPUT:
            raise ValueError
        envelope = json.loads(raw_input)
        body = envelope['body'].encode('utf-8')
        if len(body) > MAX_REQUEST_BYTES:
            raise ValueError
        key = envelope['api_key']
        timeout = envelope['timeout']
        request = Request(ENDPOINT, data=body, method='POST', headers={
            'Authorization': 'Bearer ' + key,
            'Content-Type': 'application/json', 'Accept': 'application/json',
        })
        # Default trust store, hostname checking and certificate verification stay on.
        opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
        try:
            with opener.open(request, timeout=timeout) as response:
                status = response.status
                _emit({'http_status': status})
                if status != 200:
                    _emit({'error_code': http_error_code(status), 'http_status': status})
                    return
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            status = error.code
            error.close()  # Do not read error bodies/headers: they may echo the key.
            _emit({'error_code': http_error_code(status), 'http_status': status})
            return
        if len(raw) > MAX_RESPONSE_BYTES:
            _emit({'error_code': 'RESPONSE_TOO_LARGE', 'http_status': status})
        else:
            _emit({'http_status': status, 'body_b64': base64.b64encode(raw).decode('ascii')})
    except (TimeoutError, socket.timeout):
        _emit({'error_code': 'PROVIDER_TIMEOUT', 'http_status': status})
    except (URLError, OSError, ValueError, TypeError, KeyError, RecursionError):
        _emit({'error_code': 'PROVIDER_UNAVAILABLE', 'http_status': status})
    except BaseException:
        # No traceback, repr, key, payload or arbitrary exception text crosses IPC.
        _emit({'error_code': 'PROVIDER_UNAVAILABLE', 'http_status': status})


if __name__ == '__main__':
    main()
