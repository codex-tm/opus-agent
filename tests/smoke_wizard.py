"""E2E do wizard custom: servidor falso com /models + input pipado."""
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


class FakeEndpoint(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith("/models"):
            payload = {"data": [{"id": "meu-modelo-1"}, {"id": "meu-modelo-2"}]}
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_wizard_custom_fetch_models():
    srv = HTTPServer(("127.0.0.1", 0), FakeEndpoint)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")

    # fluxo: /wizard -> 1 (provedor) -> 7 (custom) -> base_url -> key vazia -> 1 (modelo) -> 0 salva -> /sair
    stdin = f"/wizard\n1\n7\nhttp://127.0.0.1:{port}/v1\n\n1\n0\n/sair\n"
    proc = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input=stdin,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", proc.stdout + proc.stderr)
    assert proc.returncode == 0, out[-3000:]

    saved = json.loads((Path(fake_home) / ".opus" / "config.json").read_text(encoding="utf-8"))
    assert saved["default_provider"] == "custom", saved
    assert saved["default_model"] == "meu-modelo-1", saved
    assert saved["endpoints"]["custom"]["base_url"] == f"http://127.0.0.1:{port}/v1", saved
    print("PASS test_wizard_custom_fetch_models")


def test_input_setas_pipe():
    """Prompt pipado: a linha volta limpa (sem travar sem TTY)."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    with create_pipe_input() as inp:
        inp.send_text("ola mundo\n")
        s = PromptSession(input=inp, output=DummyOutput())
        r = s.prompt("> ")
        assert r == "ola mundo", r
    print("PASS test_input_setas_pipe")


if __name__ == "__main__":
    test_wizard_custom_fetch_models()
    test_input_setas_pipe()
