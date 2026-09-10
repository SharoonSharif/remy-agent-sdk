"""Run both example apps against a local model peer and a real frozen Core.

Usage: REMY_CORE=/path/to/core python3 scripts/smoke.py
Requires python/.venv and typescript/node_modules to be installed first.
No provider credentials or external model requests are used.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]

# Import examples without running their CLI entry points, then inject the local
# peer explicitly. Consumer configuration always points at the development API.
PYTHON_RUNNER = """
import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from remy import Auth

path = Path(sys.argv[1])
sys.path.insert(0, str(path.parent))
from config import options
config = options()
assert config["auth"].gateway == "https://dev-api.corepass.com/edge/v1"
os.environ["DEMO_GATEWAY"] = "https://unused.invalid"
assert options()["auth"].gateway == "https://dev-api.corepass.com/edge/v1"
config["auth"] = Auth(token=os.environ["DEMO_TOKEN"], gateway=sys.argv[2])
spec = importlib.util.spec_from_file_location("demo", path)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
asyncio.run(demo.main(config))
"""

TYPESCRIPT_RUNNER = """
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const url = pathToFileURL(process.argv[2]);
const { options } = await import(new URL('./config.ts', url).href);
const config = options();
assert.equal(config.auth.gateway, 'https://dev-api.corepass.com/edge/v1');
process.env.DEMO_GATEWAY = 'https://unused.invalid';
assert.equal(options().auth.gateway, 'https://dev-api.corepass.com/edge/v1');
config.auth = { ...config.auth, gateway: process.argv[3] };
const demo = await import(url.href);
await demo.main(config);
"""

#: (example name, a substring its stdout must contain). One row per scenario;
#: the run is this table times the two languages. An expected substring rather
#: than exact output, because an example may legitimately print more.
EXAMPLES = (
    ("hello", "Demo reply: ready."),
    ("streaming", "Demo reply: ready."),
    ("custom_tool", "Local add(2, 3) = 5"),
    ("models", "demo-model-a"),
    ("one_shot", "Demo reply: ready."),
    ("events", "thinking delta"),
    ("configuration", "configured cwd"),
    ("sessions", "second turn saw turn=2"),
    ("extending", "tool dispatched as: mcp__local__multiply"),
    ("errors", "request_id: req-demo-1"),
    ("permissions", "resumed after approval"),
)


class ModelPeer(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _json(self, payload, status=200):
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    #: Served by GET <path>/models. Two entries, because a one-entry list
    #: cannot catch a parser that returns only its first result.
    CATALOG = [
        {"id": "demo-model-a", "owned_by": "demo-provider"},
        {"id": "demo-model-b", "owned_by": "other-provider"},
    ]

    def do_GET(self):
        # Routing by path, which do_POST already does for /tasks. Serving one
        # body from every path let a wrong URL pass as a right one.
        if self.path.rstrip("/").endswith("/models"):
            self._json({"object": "list", "data": type(self).CATALOG})
            return
        self._json({"data": []})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.headers.get("Authorization") != "Bearer local-demo-token":
            self.send_error(401)
            return
        # config.withTask/with_task opens a usage task before connecting. It
        # has to resolve HERE rather than against the real gateway, or this
        # script stops being the offline check it advertises.
        if self.path.rstrip("/").endswith("/tasks"):
            self._json({"task_id": "task_local_demo"}, status=201)
            return
        prompt = " ".join(
            str(m.get("content") or "") for m in body.get("messages", [])
        )
        # Selected by prompt text: the prompt is the only channel an example
        # controls all the way through the Core to here.
        if "[[fail]]" in prompt:
            payload = json.dumps({"error": {
                "code": 42901, "type": "rate_limited",
                "message": "demo rate limit", "request_id": "req-demo-1",
            }}).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "2")
            self.send_header("X-Request-Id", "req-demo-1")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        used_tool = any(m["role"] == "tool" for m in body["messages"])
        tool_call = bool(body.get("tools")) and not used_tool
        if tool_call:
            # Call a tool the request actually offers, not a name hard-coded
            # regardless of what's registered. extending.py/ts registers only
            # "multiply" and "mcp__local__multiply" -- calling "add"
            # unconditionally (the old behaviour) got back "tool 'add' not
            # available in this sub-agent" from the real Core, so the local
            # callback and the sdk-MCP path were never exercised by this
            # harness. custom_tool/events register only "add", so the
            # fallback keeps those rows exactly as before.
            offered = {
                t.get("function", {}).get("name")
                for t in (body.get("tools") or [])
                if isinstance(t, dict)
            }
            import sys as _s; print(f"[probe] offered={sorted(offered)}", file=_s.stderr)
            # NAMESPACED first. `extending` offers both spellings, so
            # preferring the bare "multiply" meant the sdk-MCP registration was
            # constructed and never dispatched -- the one thing that scenario
            # exists to demonstrate. The bare name still has coverage: nothing
            # else registers an MCP server, so custom_tool/events/permissions
            # fall through to "add" exactly as before.
            name = next(
                (n for n in ("mcp__local__multiply", "multiply", "add") if n in offered),
                "add",
            )
            arguments = '{"a":6,"b":7}' if "multiply" in name else '{"a":2,"b":3}'
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "demo-add-1", "type": "function",
                "function": {"name": name, "arguments": arguments},
            }]}
        else:
            # Turn count in the reply, so "the conversation continued" is
            # observable. With one canned answer, a resumed session and a fresh
            # one are indistinguishable and an assertion on either is empty.
            turns = sum(1 for m in body.get("messages", []) if m.get("role") == "user")
            if used_tool:
                # Echo the tool's own return value rather than a value
                # hard-coded for one specific tool call -- this way the reply
                # is only ever right if the tool actually ran and its result
                # made it back here, whether that tool was "add" or
                # "multiply"/"mcp__local__multiply".
                tool_results = [m for m in body["messages"] if m.get("role") == "tool"]
                content = f"The result is {tool_results[-1].get('content')}."
            else:
                content = f"Demo reply: ready. turn={turns}"
            message = {"role": "assistant", "content": content}
        finish = "tool_calls" if tool_call else "stop"
        base = {"id": "demo-response", "created": 0, "model": "gpt-4o"}
        usage = {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            delta = dict(message)
            if tool_call:
                delta["tool_calls"] = [{"index": 0, **call} for call in message["tool_calls"]]
            chunks = [
                {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": finish}], "usage": usage},
            ]
            if "[[thinking]]" in prompt:
                thinking = {**base, "object": "chat.completion.chunk", "choices": [
                    {"index": 0, "delta": {"reasoning_content": "Considering."},
                     "finish_reason": None}]}
                self.wfile.write(("data: " + json.dumps(thinking) + "\n\n").encode())
                self.wfile.flush()
            for index, chunk in enumerate(chunks):
                if index and "[[slow]]" in prompt:
                    # A reply that finishes instantly cannot be cancelled, and a
                    # test that cancels a finished run proves nothing.
                    time.sleep(0.4)
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            payload = json.dumps({**base, "object": "chat.completion", "choices": [
                {"index": 0, "message": message, "finish_reason": finish},
            ], "usage": usage}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)


def main():
    core = os.environ.get("REMY_CORE")
    if not core or not Path(core).is_file():
        raise SystemExit("Set REMY_CORE to a compatible frozen Core executable")
    python = ROOT / "python/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        raise SystemExit("Install the Python example environment first")
    server = ThreadingHTTPServer(("127.0.0.1", 0), ModelPeer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="remy-example-smoke-") as state:
            env = dict(os.environ, REMY_CORE=str(Path(core).resolve()),
                       DEMO_MODEL="openai/gpt-4o", DEMO_TOKEN="local-demo-token",
                       DEMO_PRODUCT_ID="local-demo-product",
                       COREPASS_HOME=state, HARNESS_TRACE_LLM_IO="0", HARNESS_UI_STREAM="1")
            env.pop("PYTHONPATH", None)
            env.pop("DEMO_GATEWAY", None)
            gateway = f"http://127.0.0.1:{server.server_port}/v1"
            for language, executable, extension in [
                ("python", [str(python), "-c", PYTHON_RUNNER], "py"),
                ("typescript", ["node", "--experimental-strip-types", "--input-type=module",
                                "-e", TYPESCRIPT_RUNNER, "smoke-harness"], "ts"),
            ]:
                for example, expected in EXAMPLES:
                    filename = example.replace("_", "-") if language == "typescript" else example
                    path = ROOT / language / "examples" / f"{filename}.{extension}"
                    result = subprocess.run([*executable, str(path), gateway],
                                            cwd=ROOT / language, env=env, text=True,
                                            capture_output=True, timeout=90)
                    if result.returncode:
                        raise RuntimeError(f"{language}/{filename} failed:\n{result.stderr}")
                    if expected not in result.stdout:
                        raise AssertionError(f"{language}/{filename} missing expected output:\n{result.stdout}")
                    print(f"PASS {language}/{filename}", flush=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
