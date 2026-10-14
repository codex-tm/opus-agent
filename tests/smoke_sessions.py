"""E2E de sessoes: cria numa run, lista e resume noutra, com SQLite."""
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
SEEN = {"count": 0, "history_len": 0}


class FakeLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        SEEN["count"] += 1
        SEEN["history_len"] = len(body.get("messages", []))
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            data = json.dumps({"choices": [{"delta": {"content": "resposta um"}}]}).encode()
            self.wfile.write(b"data: " + data + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            SEEN["count"] += 1
            SEEN["history_len"] = len(body.get("messages", []))
            data = json.dumps({"choices": [{"message": {"role": "assistant", "content": "resposta um"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def log_message(self, *a):
        pass


def _run(env, stdin):
    return subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input=stdin, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=90,
    )


def test_sessions_persist_and_resume():
    srv = HTTPServer(("127.0.0.1", 0), FakeLLM)
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
        "reasoning": "off",
    }), encoding="utf-8")
    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")

    # run 1: fala algo (cria sessao no banco)
    p1 = _run(env, "primeira mensagem\n/sair\n")
    assert p1.returncode == 0, p1.stdout[-1500:] + p1.stderr[-800:]
    assert (Path(fake_home) / ".opus" / "sessions.db").exists(), "sessions.db nao criado"

    # run 2: lista e resume a sessao 1, confirma que o modelo recebeu o historico
    SEEN["count"] = 0
    SEEN["history_len"] = 0
    p2 = _run(env, "/sessions\n/resume 1\nsegunda mensagem\n/sair\n")
    out = ANSI.sub("", p2.stdout + p2.stderr)
    assert p2.returncode == 0, out[-2000:]
    assert "primeira mensagem" in out, f"lista nao mostrou o nome:\n{out}"
    # system + user1 + assistant1 + user2 = 4 mensagens enviadas na ultima chamada
    assert SEEN["history_len"] == 4, f"historico errado: {SEEN}"
    print("PASS test_sessions_persist_and_resume")


if __name__ == "__main__":
    test_sessions_persist_and_resume()
