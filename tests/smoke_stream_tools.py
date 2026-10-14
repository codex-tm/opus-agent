"""E2E do streaming com tool_call em SSE."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


class StreamAgentLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        has_tool = any(m.get("role") == "tool" for m in body.get("messages", []))
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            chunks = [
                {"choices": [{"delta": {"content": "vou ler "}}]},
                {"choices": [{"delta": {"content": "o arquivo."}}]},
            ]
            if not has_tool:
                tc1 = {"index": 0, "id": "c1", "type": "function",
                       "function": {"name": "write_file", "arguments": '{"filepath":"stream.py","content":"s=1\\n"}'}}
                chunks += [{"choices": [{"delta": {"tool_calls": [tc1]}}]}]
            else:
                chunks = [{"choices": [{"delta": {"content": "criei o arquivo."}}]}]
            for c in chunks:
                self.wfile.write(b"data: " + json.dumps(c).encode() + b"\n\n")
                self.wfile.flush()
                time.sleep(0.02)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        if not has_tool:
            payload = json.dumps({"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "write_file", "arguments": json.dumps({"filepath": "stream.py", "content": "s=1\n"})}}
            ]}}]}).encode()
        else:
            payload = json.dumps({"choices": [{"message": {"role": "assistant", "content": "criei o arquivo."}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


def test_stream_durante_tool_call():
    srv = HTTPServer(("127.0.0.1", 0), StreamAgentLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    cfg = Path(fake_home) / ".opus" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({
        "default_provider": "deepseek", "default_model": "m",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{port}/v1"}},
        "reasoning": "off",
        "auto_approve_tools": True,
    }), encoding="utf-8")
    work = tempfile.mkdtemp(prefix="opus_work_")
    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")
    p = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input="crie stream.py\n/sair\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=work, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", p.stdout + p.stderr)
    assert p.returncode == 0, out[-2000:]
    assert "criei o arquivo" in out, out[-800:]
    assert (Path(work) / "stream.py").read_text() == "s=1\n", "arquivo nao criado"
    print("PASS test_stream_durante_tool_call")


if __name__ == "__main__":
    test_stream_durante_tool_call()
