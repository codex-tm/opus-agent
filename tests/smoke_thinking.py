"""E2E + unit: thinking do modelo (reasoning_content/reasoning) deve chegar na tela.

Cobre:
1. chat_stream emite ("think", ...) quando o delta traz reasoning_content ou reasoning
2. chat() (nao-stream) captura reasoning_content/reasoning no LLMDone
3. E2E piped: subprocesso main.py com servidor falso que manda reasoning_content
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
sys.path.insert(0, str(ROOT))
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

THINK_TEXT = "estou raciocinando sobre o pedido"
ANSWER_TEXT = "a resposta final e 42"

SSE_CHUNKS = [
    {"choices": [{"delta": {"reasoning_content": "estou raciocinando "}}]},
    {"choices": [{"delta": {"reasoning_content": "sobre o pedido"}}]},
    {"choices": [{"delta": {"reasoning": "via campo reasoning "}}]},
    {"choices": [{"delta": {"content": "a resposta "}}]},
    {"choices": [{"delta": {"content": "final e 42"}}]},
]

JSON_BODY = {
    "choices": [{
        "message": {
            "role": "assistant",
            "content": ANSWER_TEXT,
            "reasoning_content": THINK_TEXT,
        }
    }]
}


class FakeStream(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not body.get("stream"):
            data = json.dumps(JSON_BODY).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for c in SSE_CHUNKS:
            data = json.dumps(c).encode()
            self.wfile.write(b"data: " + data + b"\n\n")
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, *a):
        pass


def _start_server():
    srv = HTTPServer(("127.0.0.1", 0), FakeStream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _config(port):
    return {
        "default_provider": "deepseek",
        "default_model": "fake-reasoner",
        "api_keys": {"deepseek": "k"},
        "endpoints": {"deepseek": {"base_url": f"http://127.0.0.1:{port}/v1"}},
        "reasoning": "high",
    }


def test_stream_emits_think():
    """chat_stream deve emitir eventos ('think', ...) para reasoning_content e reasoning."""
    from opus.core.client import chat_stream
    srv, port = _start_server()
    try:
        events = list(chat_stream(_config(port), [{"role": "user", "content": "oi"}]))
    finally:
        srv.shutdown()
    kinds = [k for k, _ in events]
    assert "think" in kinds, f"sem evento think: {events}"
    think_text = "".join(d for k, d in events if k == "think")
    full_text = "".join(d for k, d in events if k == "text")
    assert "estou raciocinando sobre o pedido" in think_text, think_text
    assert "via campo reasoning" in think_text, think_text
    assert "a resposta final e 42" in full_text, full_text
    print("PASS test_stream_emits_think")


def test_chat_captures_reasoning():
    """chat() nao-stream deve preencher LLMDone.reasoning."""
    from opus.core.client import chat
    srv, port = _start_server()
    try:
        result = chat(_config(port), [{"role": "user", "content": "oi"}])
    finally:
        srv.shutdown()
    assert result.content == ANSWER_TEXT, result.content
    assert hasattr(result, "reasoning"), "LLMDone sem atributo reasoning"
    assert result.reasoning == THINK_TEXT, repr(result.reasoning)
    print("PASS test_chat_captures_reasoning")


def test_e2e_piped_shows_think():
    """E2E piped (nao-TTY): o raciocinio do modelo deve aparecer na saida."""
    srv, port = _start_server()
    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    cfg_dir = Path(fake_home) / ".opus"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps(_config(port)), encoding="utf-8")

    env = dict(os.environ, USERPROFILE=fake_home, HOME=fake_home, NO_COLOR="1", COLUMNS="90")
    proc = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input="quanto vale a vida?\n/sair\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=90,
    )
    srv.shutdown()
    out = ANSI.sub("", proc.stdout + proc.stderr)
    assert proc.returncode == 0, out[-2000:]
    assert THINK_TEXT in out, f"raciocinio sumiu da saida:\n{out[-1500:]}"
    assert ANSWER_TEXT in out, f"resposta sumiu da saida:\n{out[-1500:]}"
    assert out.index(THINK_TEXT) < out.index(ANSWER_TEXT), "think veio depois da resposta"
    print("PASS test_e2e_piped_shows_think")


if __name__ == "__main__":
    test_stream_emits_think()
    test_chat_captures_reasoning()
    test_e2e_piped_shows_think()
