"""E2E: em TTY simulado, markdown nao deve vazar cru (** e ```) na saida final;
o texto deve sair renderizado pelo md_render.
"""
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

CHUNKS = [
    "Reposta:\n\n", "**negrito** e `codigo`:\n\n",
    "```py\n", "x = 1\n", "```\n",
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
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, *a):
        pass


def test_tty_no_raw_markdown():
    """Force terminal mas sem ANSI real: saida nao pode conter ** nem ```."""
    srv = HTTPServer(("127.0.0.1", 0), FakeStream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    cfg_dir = Path(fake_home) / ".opus"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({
        "default_provider": "deepseek",
        "default_model": "fake",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{port}/v1"}},
        "reasoning": "off",
    }), encoding="utf-8")

    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, COLUMNS="90",
               FORCE_TERMINAL="1")
    proc = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input="oi\n/sair\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", proc.stdout + proc.stderr)
    assert proc.returncode == 0, out[-2000:]
    assert "**negrito**" not in out, f"markdown cru vazou:\n{out[-1500:]}"
    assert "```" not in out, f"fence cru vazou:\n{out[-1500:]}"
    assert "negrito" in out, f"texto sumiu:\n{out[-1500:]}"
    print("PASS test_tty_no_raw_markdown")


if __name__ == "__main__":
    test_tty_no_raw_markdown()
