"""E2E do motor: cliente OpenAI-compat contra servidor HTTP falso + markdown."""
import json
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

REPLY = (
    "Claro! Aqui vai um **exemplo** com `codigo`:\n"
    "\n"
    "```python\n"
    "def ola():\n"
    "    return 'mundo'\n"
    "```\n"
    "\n"
    "- item um\n"
    "- item dois\n"
)


class FakeLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        assert body["model"] == "fake-model", body
        assert body["messages"][-1]["role"] == "user"
        payload = {
            "choices": [{"message": {"role": "assistant", "content": REPLY}}]
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_agente_responde_e_renderiza():
    srv = HTTPServer(("127.0.0.1", 0), FakeLLM)
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
        "system_instructions": "Responda em pt-BR.",
    }), encoding="utf-8")

    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)

    import os
    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")
    proc = subprocess.run(
        [str(py), str(ROOT / "main.py")],
        input="me da um exemplo\n/sair\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=60,
    )
    srv.shutdown()
    out = ANSI.sub("", proc.stdout + proc.stderr)
    assert proc.returncode == 0, out[-2000:]
    assert "def ola():" in out, f"resposta do modelo ausente:\n{out}"
    assert "**exemplo**" not in out, "markdown cru vazou na saida"
    assert "```" not in out, "fence de codigo cru vazou na saida"
    assert "item um" in out
    print("PASS test_agente_responde_e_renderiza")


if __name__ == "__main__":
    test_agente_responde_e_renderiza()
