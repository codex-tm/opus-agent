"""E2E do agent loop: tool calling real, ask_user e diff."""
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
CALLS = {"n": 0}


def ok(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def tool_call(name, args):
    return json.dumps({
        "choices": [{"message": {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": f"call_{name}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }],
        }}]
    })


class AgentLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        # so responde tool_call quando ainda nao veio tool result
        has_tool_result = any(m.get("role") == "tool" for m in body.get("messages", []))
        names = [tc["function"]["name"] for m in body.get("messages", [])
                 for tc in (m.get("tool_calls") or [])]
        if "escopo" in json.dumps(body.get("messages", "")) and "ask_user" not in names:
            payload = tool_call("ask_user", {"question": "Qual o escopo?"})
        elif "crie arq.py" in json.dumps(body.get("messages", "")) and not has_tool_result:
            payload = tool_call("write_file", {"filepath": "arq.py", "content": "x=1\n"})
        else:
            payload = json.dumps(ok("entendido"))
        data = payload.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def _run(env, cwd, stdin):
    return subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input=stdin, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, cwd=cwd, timeout=90,
    )


def test_agent_loop_tools_and_ask():
    srv = HTTPServer(("127.0.0.1", 0), AgentLLM)
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
        "auto_approve_tools": True,
    }), encoding="utf-8")

    work = tempfile.mkdtemp(prefix="opus_work_")
    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")

    # 1) ask_user: o agente pergunta o escopo e depois finaliza
    p = _run(env, work, "escopo: aumenta cobertura\nmeu escopo e X\n/sair\n")
    out = ANSI.sub("", p.stdout + p.stderr)
    assert p.returncode == 0, out[-2000:]
    assert "Qual o escopo?" in out, f"ask_user nao perguntou:\n{out[-800:]}"
    assert "entendido" in out, f"nao finalizou:\n{out[-800:]}"

    # 2) write_file cria o arquivo e mostra diff (+verde)
    p = _run(env, work, "crie arq.py\n/sair\n")
    out = ANSI.sub("", p.stdout + p.stderr)
    assert p.returncode == 0, out[-2000:]
    assert (Path(work) / "arq.py").read_text() == "x=1\n", "arquivo nao criado"
    assert "arq.py" in out, f"diff nao mostrou o path:\n{out[-600:]}"
    print("PASS test_agent_loop_tools_and_ask")


if __name__ == "__main__":
    test_agent_loop_tools_and_ask()
