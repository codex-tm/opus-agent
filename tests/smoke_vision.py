"""E2E de visao: imagem de arquivo -> mensagem multimodal; e sem suporte."""
import base64
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
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
SEEN = {"multimodal": False}


class VLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        msgs = body.get("messages", [])
        SEEN["multimodal"] = any(
            isinstance(m.get("content"), list) for m in msgs if m.get("role") == "user"
        )
        data = json.dumps({"choices": [{"message": {"role": "assistant", "content": "vi a imagem"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def _prep():
    srv = HTTPServer(("127.0.0.1", 0), VLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    cfg = Path(fake_home) / ".opus" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({
        "default_provider": "deepseek",
        "default_model": "gpt-4o",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1"}},
        "reasoning": "off",
    }), encoding="utf-8")
    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")
    return srv, env


def test_visao_caminho_e_payload():
    srv, env = _prep()
    work = tempfile.mkdtemp(prefix="opus_work_")
    img = Path(work) / "img.png"
    img.write_bytes(PNG_1PX)
    stdin = f"/visao\n{img}\no que tem?\n/sair\n"
    p = subprocess.run(
        [str(PY), str(ROOT / "main.py")], input=stdin,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", p.stdout + p.stderr)
    assert p.returncode == 0, out[-2000:]
    assert SEEN["multimodal"], "payload nao trouxe imagem"
    assert "vi a imagem" in out, out[-600:]
    print("PASS test_visao_caminho_e_payload")


def test_visao_sem_suporte():
    srv, env = _prep()
    cfg = Path(env["USERPROFILE"]) / ".opus" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({
        "default_provider": "deepseek", "default_model": "deepseek-coder",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1"}},
    }), encoding="utf-8")
    work = tempfile.mkdtemp(prefix="opus_work_")
    img = Path(work) / "img.png"
    img.write_bytes(PNG_1PX)
    stdin = f"/visao\n{img}\n/sair\n"
    p = subprocess.run(
        [str(PY), str(ROOT / "main.py")], input=stdin,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", p.stdout + p.stderr)
    assert "nao suporta visao" in out, out[-600:]
    print("PASS test_visao_sem_suporte")


if __name__ == "__main__":
    test_visao_caminho_e_payload()
    test_visao_sem_suporte()
