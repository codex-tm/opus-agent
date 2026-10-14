"""E2E do agent loop chamando web_browse com Playwright real (no LLM)."""
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


def ok(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def tool_call(name, args):
    return json.dumps({
        "choices": [{"message": {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }],
        }}]
    })


class BrowserLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        has_tool = any(m.get("role") == "tool" for m in body.get("messages", []))
        if "abra example.com" in json.dumps(body.get("messages", "")) and not has_tool:
            payload = tool_call("web_browse", {"url": "https://example.com", "acao": "ler"})
        else:
            payload = json.dumps(ok("li: Example Domain"))
        data = payload.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_web_browse_no_agent_loop():
    srv = HTTPServer(("127.0.0.1", 0), BrowserLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    cfg = Path(fake_home) / ".opus" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({
        "default_provider": "deepseek", "default_model": "m",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{port}/v1"}},
        "reasoning": "off", "auto_approve_tools": True,
    }), encoding="utf-8")
    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")

    p = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input="abra example.com\n/sair\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=120,
    )
    srv.shutdown()
    out = ANSI.sub("", p.stdout + p.stderr)
    assert p.returncode == 0, out[-2000:]
    assert "Example Domain" in out, f"nao viu o conteudo:\n{out[-900:]}"
    assert "li: Example Domain" in out, out[-600:]
    print("PASS test_web_browse_no_agent_loop")


if __name__ == "__main__":
    test_web_browse_no_agent_loop()
