"""One read-only tool call in an expendable interpreter; private pipe protocol.

Launched with Python -I by the supervisor, never imported as an application entry
point. The worker inherits no provider credentials. Only a fixed error envelope is
emitted for any failure; no arguments, paths, bodies or exception text cross IPC.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAX_INPUT_BYTES = 16 * 1024
MAX_OUTPUT_BYTES = 128 * 1024
_FAILURE = {
    "ok": False,
    "error": {
        "code": "TOOL_FAILURE",
        "message": "Não foi possível consultar essa informação. Consulte a equipe da loja.",
        "details": {},
    },
    "meta": {},
}


def _failure(code):
    return {**_FAILURE, "error": {**_FAILURE["error"], "code": code}}


def _emit(value) -> None:
    output = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
    if len(output) > MAX_OUTPUT_BYTES:
        output = json.dumps(_failure("TOOL_OUTPUT_TOO_LARGE"), ensure_ascii=False).encode("utf-8") + b"\n"
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


def main() -> None:
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError
        packet = json.loads(raw)
        if not isinstance(packet, dict) or set(packet) != {"name", "arguments"}:
            raise ValueError
        name, arguments = packet["name"], packet["arguments"]
    except BaseException:
        _emit(_failure("WORKER_PROTOCOL_ERROR"))
        return
    try:
        from app.agent.tool_registry import ToolRegistry

        result = ToolRegistry().dispatch(name, arguments)
        if not isinstance(result, dict) or type(result.get("ok")) is not bool:
            raise ValueError
        _emit(result)
    except BaseException:
        # Never let a traceback, path, argument or exception string reach the parent.
        _emit(_FAILURE)


if __name__ == "__main__":
    main()
