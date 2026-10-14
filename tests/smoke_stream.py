"""E2E do streaming: servidor SSE falso e saida em tempo real."""
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

CHUNKS = [
    "Claro! ", "Aqui vai ", "**um exemplo** ", "com `codigo`:\n\n",
    "```python\n", "def ola():\n", "    return 'mundo'\n", "```\n\n",
    "- item um\n", "- item dois\n",
]


class FakeStream(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not body.get("stream"):
            data = json.dumps({"choices": [{"message": {"role": "assistant", "content": "".join(CHUNKS)}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for c in CHUNKS:
            data = json.dumps({"choices": [{"delta": {"content": c}}]}).encode()
            self.wfile.write(b"data: " + data + b"\n\n")
            self.wfile.flush()
            time.sleep(0.02)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, *a):
        pass


def test_streaming_final_markdown():
    srv = HTTPServer(("127.0.0.1", 0), FakeStream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    cfg_dir = Path(fake_home) / ".opus"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({
        "default_provider": "deepseek",
        "default_model": "fake-model",
        "api_keys": {"deepseek": "sk-fake"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{port}/v1"}},
    }), encoding="utf-8")

    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")
    proc = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input="teste\n/sair\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", proc.stdout + proc.stderr)
    assert proc.returncode == 0, out[-2000:]
    assert "def ola():" in out, f"codigo ausente:\n{out}"
    assert "**um exemplo**" not in out, "markdown cru vazou"
    assert "```" not in out, "fence cru vazou"
    print("PASS test_streaming_final_markdown")


if __name__ == "__main__":
    test_streaming_final_markdown()
