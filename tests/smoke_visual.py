"""E2E visual smoke: roda o app pipado num HOME falso e asserita a saida."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def run_session(stdin_text: str) -> str:
    env = dict(os.environ)
    fake_home = tempfile.mkdtemp(prefix="opus_home_")
    env["USERPROFILE"] = fake_home
    env["HOME"] = fake_home
    env["FORCE_COLOR"] = "1"
    env["COLUMNS"] = "100"
    proc = subprocess.run(
        [str(PY), str(ROOT / "main.py")],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    out = ANSI.sub("", proc.stdout + proc.stderr)
    assert proc.returncode == 0, out[-2000:]
    return out


def banner_lines(out: str) -> list:
    """Linhas entre o inicio e a primeira linha do prompt."""
    idx = out.find(">")
    assert idx != -1, f"prompt '>' nao encontrado:\n{out[:3000]}"
    return [l for l in out[:idx].splitlines() if l.strip()]


def test_boot_enxuto():
    out = run_session("/sair\n")
    assert "SISTEMA AUT" not in out, "subtitle antigo ainda presente"
    assert "CORE EDITION" not in out, "subtitle antigo ainda presente"
    assert "PROVEDOR" not in out, "cards de status ainda presentes"
    assert "WORKSPACE" not in out, "cards de status ainda presentes"
    assert "CONTROLES" not in out, "footer/cards ainda presentes"
    assert "PRESSIONE" not in out.upper(), "footer de botoes ainda presente"
    boot = banner_lines(out)
    assert len(boot) <= 8, f"boot tem {len(boot)} linhas nao-vazias (max 8):\n{boot}"
    return out


def test_prompt_limpo():
    out = run_session("/sair\n")
    assert "OPUS (" not in out, "prompt antigo 'OPUS (ANTHROPIC) »' ainda presente"
    assert ">" in out, "prompt novo '>' ausente"


def test_resposta_sem_panel():
    out = run_session("qualquer coisa\n/sair\n")
    assert "Sessão Ativa" not in out, "panel de resposta antigo ainda presente"


def test_tools_limpo():
    out = run_session("/tools\n/sair\n")
    assert "CENTRAL DE FERRAMENTAS" not in out, "header antigo de /tools ainda presente"
    assert "READ_FILE" in out or "read_file" in out, "listagem de ferramentas ausente"


def test_wizard_limpo():
    out = run_session("/wizard\n0\n/sair\n")
    assert "CENTRAL DE CONFIGURA" not in out, "header antigo do wizard ainda presente"


if __name__ == "__main__":
    tests = [
        test_boot_enxuto,
        test_prompt_limpo,
        test_resposta_sem_panel,
        test_tools_limpo,
        test_wizard_limpo,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    sys.exit(1 if failed else 0)
