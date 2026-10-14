"""E2E unit: tool_call em streaming TTY deve vir no formato OpenAI
({id, type:"function", function:{name,arguments}}) — se nao, o agent.py
nao encontra o nome da fn e o historico volta pro servidor invalido (400).
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from opus.core.client import chat_stream  # noqa: E402

SSE_CHUNKS = [
    {"choices": [{"delta": {"content": "vou criar "}}]},
    {"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": "c1", "type": "function",
         "function": {"name": "write_file", "arguments": '{"filepath":"a.py"'}}
    ]}}]},
    {"choices": [{"delta": {"tool_calls": [
        {"index": 0, "function": {"arguments": ',"content":"x"}'}}
    ]}}]},
]


class FakeStream(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for c in SSE_CHUNKS:
            data = json.dumps(c).encode()
            self.wfile.write(b"data: " + data + b"\n\n")
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, *a):
        pass


def test_stream_toolcall_openai_format():
    srv = HTTPServer(("127.0.0.1", 0), FakeStream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    config = {
        "default_provider": "deepseek",
        "default_model": "m",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{port}/v1"}},
        "reasoning": "off",
    }
    events = list(chat_stream(config, [{"role": "user", "content": "oi"}]))
    srv.shutdown()

    tool_events = [d for k, d in events if k == "toolcall"]
    assert tool_events, f"sem toolcall: {events}"
    call = tool_events[0]
    assert call.get("type") == "function", f"call sem type=function: {call}"
    fn = call.get("function") or {}
    assert fn.get("name") == "write_file", f"fn sem name: {call}"
    assert fn.get("arguments") == '{"filepath":"a.py","content":"x"}', f"args: {call}"
    print("PASS test_stream_toolcall_openai_format")


if __name__ == "__main__":
    test_stream_toolcall_openai_format()
