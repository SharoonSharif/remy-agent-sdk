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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


class ModelPeer(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"data": []}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.headers.get("Authorization") != "Bearer local-demo-token":
            self.send_error(401)
            return
        used_tool = any(m["role"] == "tool" for m in body["messages"])
        tool_call = bool(body.get("tools")) and not used_tool
        if tool_call:
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "demo-add-1", "type": "function",
                "function": {"name": "add", "arguments": '{"a":2,"b":3}'},
            }]}
        else:
            message = {"role": "assistant", "content": "The result is 5." if used_tool else "Demo reply: ready."}
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
            for chunk in chunks:
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
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
                       DEMO_GATEWAY=f"http://127.0.0.1:{server.server_port}/v1",
                       COREPASS_HOME=state, HARNESS_TRACE_LLM_IO="0", HARNESS_UI_STREAM="1")
            env.pop("PYTHONPATH", None)
            for language, executable, extension in [
                ("python", [str(python)], "py"),
                ("typescript", ["node", "--experimental-strip-types"], "ts"),
            ]:
                for example in ("hello", "streaming", "custom_tool"):
                    filename = example.replace("_", "-") if language == "typescript" else example
                    result = subprocess.run([*executable, f"examples/{filename}.{extension}"],
                                            cwd=ROOT / language, env=env, text=True,
                                            capture_output=True, timeout=90)
                    if result.returncode:
                        raise RuntimeError(f"{language}/{filename} failed:\n{result.stderr}")
                    expected = "Local add(2, 3) = 5" if example == "custom_tool" else "Demo reply: ready."
                    if expected not in result.stdout:
                        raise AssertionError(f"{language}/{filename} missing expected output:\n{result.stdout}")
                    print(f"PASS {language}/{filename}", flush=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
