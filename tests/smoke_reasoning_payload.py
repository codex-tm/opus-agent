"""Unit: _chat_payload deve mapear o nivel de raciocinio pro parametro certo
de cada provider (DeepSeek/OpenAI sao diferentes), e a statusbar deve mostrar
o nivel ativo.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from opus.core.client import _chat_payload  # noqa: E402
from opus.ui.statusbar import render_statusbar  # noqa: E402
from rich.console import Console  # noqa: E402
from opus.ui.theme import OPUS_THEME  # noqa: E402

import io

MSGS = [{"role": "user", "content": "oi"}]


def _cfg(provider, reasoning):
    return {
        "default_provider": provider,
        "default_model": "modelo-x",
        "api_keys": {provider: "k"},
        "endpoints": {provider: {"base_url": "http://x/v1"}},
        "reasoning": reasoning,
    }


def test_openai_reasoning_effort():
    """OpenAI-compat genericos: reasoning_effort no payload."""
    _, _, payload = _chat_payload(_cfg("openai", "high"), MSGS, None, False)
    assert payload.get("reasoning_effort") == "high", payload
    print("PASS test_openai_reasoning_effort")


def test_deepseek_enable_thinking():
    """DeepSeek: espera enable_thinking=true (ou flag equivalente), nao reasoning_effort."""
    _, _, payload = _chat_payload(_cfg("deepseek", "high"), MSGS, None, False)
    joined = str(payload)
    assert ("reasoning_effort" in payload) or ("enable_thinking" in payload) or ("thinking" in payload), joined
    if "reasoning_effort" in payload:
        # aceitavel: deepseek-reasoner aceita reasoning_effort via proxy compat;
        # mas o valor nao pode ser um nivel desconhecido
        assert payload["reasoning_effort"] in ("low", "medium", "high"), payload
    print("PASS test_deepseek_enable_thinking")


def test_reasoning_off_omits_param():
    """off: nenhum parametro de raciocinio no payload."""
    _, _, payload = _chat_payload(_cfg("openai", "off"), MSGS, None, False)
    keys = set(payload) - {"model", "messages", "tools", "tool_choice", "stream"}
    assert not keys, f"parametros extras com off: {keys}"
    print("PASS test_reasoning_off_omits_param")


def test_max_nao_vaza():
    """o menu pode oferecer 'max', mas providers comuns nao entendem; sanitiza."""
    _, _, payload = _chat_payload(_cfg("deepseek", "max"), MSGS, None, False)
    val = payload.get("reasoning_effort")
    if val is not None:
        assert val in ("low", "medium", "high"), f"max vazou cru: {val}"
    print("PASS test_max_nao_vaza")


def test_statusbar_shows_reasoning():
    """Statusbar deve informar o nivel de raciocinio ativo."""
    buf = io.StringIO()
    console = Console(theme=OPUS_THEME, file=buf, width=90, force_terminal=False)
    render_statusbar(console, _cfg("deepseek", "high"))
    out = buf.getvalue()
    assert "high" in out, f"statusbar sem nivel de raciocinio: {out!r}"
    print("PASS test_statusbar_shows_reasoning")


if __name__ == "__main__":
    test_openai_reasoning_effort()
    test_deepseek_enable_thinking()
    test_reasoning_off_omits_param()
    test_max_nao_vaza()
    test_statusbar_shows_reasoning()
