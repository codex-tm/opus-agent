"""OPUS Agent - Selecao com setas (prompt_toolkit), fallback para numero.

TTY: menu de completar com setas/baixo. Pipado: pergunta o numero via input().
O limite valido deriva da quantidade de itens, nao de tabela hardcoded.
"""

import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.validation import Validator, ValidationError

from .prompt_input import is_interactive_tty, GLYPH_PROMPT


class _NumValidator(Validator):
    def __init__(self, max_n: int):
        self.max_n = max_n

    def validate(self, document):
        t = document.text.strip()
        if t and (not t.isdigit() or int(t) < 1 or int(t) > self.max_n):
            raise ValidationError(message="numero invalido")


class _NumCompleter(Completer):
    def __init__(self, meta):
        self.meta = meta

    def get_completions(self, document, complete_event):
        t = document.text_before_cursor
        for i, display in self.meta:
            s = str(i)
            if s.startswith(t):
                yield Completion(s, start_position=-len(t), display=s, display_meta=display)


def select(console, title: str, items: list) -> str:
    """Lista numerada; setas no menu de completar validam a escolha."""
    comeback = []
    for idx, item in enumerate(items, 1):
        main, meta = item[0], (item[1] if len(item) > 1 else "")
        line = f"  {idx}  {main}"
        if meta:
            line += f"  [dim]{meta}[/]"
        console.print(line)
        comeback.append((idx, main))
    console.print()

    if not is_interactive_tty():
        sys.stdout.write(f"{GLYPH_PROMPT} ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if not line:
            return ""
        return line.strip()

    session = PromptSession(
        completer=_NumCompleter(comeback),
        validator=_NumValidator(len(comeback)),
    )
    return session.prompt(f"{GLYPH_PROMPT} ").strip()
