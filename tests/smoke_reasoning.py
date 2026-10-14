"""E2E do /raciocinio: menu via numeros e envio de reasoning_effort."""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
SEEN = {}


class FakeStream(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        SEEN["body"] = json.loads(self.rfile.read(length) or b"{}")
        data = json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_reasoning_menu_and_payload():
    srv = HTTPServer(("127.0.0.1", 0), FakeStream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    cfg = Path(fake_home) / ".opus" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({
        "default_provider": "deepseek",
        "default_model": "m",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{port}/v1"}},
        "reasoning": "medium",
    }), encoding="utf-8")

    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")
    proc = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input="/raciocinio\n4\nteste\n/sair\n",  # off,low,medium,high,max -> 4=high
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", proc.stdout + proc.stderr)
    assert proc.returncode == 0, out[-2000:]
    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["reasoning"] == "high", saved
    assert SEEN["body"].get("reasoning_effort") == "high", SEEN["body"]
    print("PASS test_reasoning_menu_and_payload")


if __name__ == "__main__":
    test_reasoning_menu_and_payload()
