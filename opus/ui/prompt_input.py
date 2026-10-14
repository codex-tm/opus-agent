"""OPUS Agent - Input interativo (prompt_toolkit): setas, historico, /completar.

Em terminal real (TTY): setas, historico e menu de autocomplete.
Com stdin pipado (testes/scripts/CI): leitura de linha simples via input().
Suporte robusto: FORCE_COLOR, TERM=dumb, NO_COLOR, CI env vars.
"""

import os
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from .help_view import COMMANDS
from .theme import COLOR_ACCENT, GLYPH_PROMPT


def is_interactive_tty() -> bool:
    """Detecção robusta de TTY interativo."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    # Respeita NO_COLOR e TERM=dumb
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    # Força modo não-interativo em CI
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS") or os.environ.get("GITLAB_CI"):
        return False
    return True


def pipe_read(label: str, default: str = "") -> str:
    """Leitura pipada: mostra label + default, le uma linha do stdin."""
    suffix = f" [{default}]" if default else ""
    sys.stdout.write(f"{label}{suffix}: ")
    sys.stdout.flush()
    try:
        line = sys.stdin.readline()
        if not line:  # EOF
            return default
        return line.rstrip("\n\r") or default
    except (EOFError, KeyboardInterrupt):
        return default


_STYLE = Style.from_dict({
    "completion-menu": f"bg:{COLOR_ACCENT} #000000",
    "completion-menu.completion": f"bg:{COLOR_ACCENT} #000000",
    "completion-menu.completion.current": "bg:#B18CFF #000000 bold",
    "completion-menu.meta": "bg:#000000 #8A8F98",
})


class SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for cmd, desc in COMMANDS:
            if cmd.startswith(text):
                yield Completion(
                    cmd, start_position=-len(text),
                    display=cmd, display_meta=desc,
                )


class OpusInput:
    """Prompt com setas, historico (cima/baixo) e autocomplete de /."""

    def __init__(self):
        self._is_tty = is_interactive_tty()
        self._session = None
        if self._is_tty:
            self._session = PromptSession(
                completer=SlashCompleter(),
                history=InMemoryHistory(),
                style=_STYLE,
                reserve_space_for_menu=8,
            )

    def read(self) -> str:
        if not self._session:
            # modo pipado: ecoa o prompt como texto puro pra manter saida limpa
            sys.stdout.write(f"{GLYPH_PROMPT} ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            if not line:  # EOF
                raise EOFError
            return line.rstrip("\n\r")
        return self._session.prompt(
            HTML(f'<style fg="{COLOR_ACCENT}"><b>{GLYPH_PROMPT}</b></style> ')
        )
