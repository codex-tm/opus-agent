"""OPUS Agent - Diff vermelho/verde pra write_file/edit_file."""

import difflib

from rich.console import Console
from rich.text import Text

from ..core import tools


def render_diff(console: Console, path: str, old: str, new: str, max_lines: int = 40) -> str:
    """Mostra -vermelho/+verde. Retorna resumo 'Nx'."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=2))

    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))

    console.print(Text(f"  {path}  ", style="bold #E6E6E6") +
                  Text(f"-{removed}", style="#FF6B7A") + Text(f" +{added}", style="#7BD88F"))
    shown = 0
    for line in diff[2:]:  # pula ---/+++
        if shown >= max_lines:
            console.print(Text(f"  ... +{len(diff) - 2 - shown} linhas", style="opus.muted"))
            break
        if line.startswith("-"):
            console.print(Text("  " + line, style="#FF6B7A"))
        elif line.startswith("+"):
            console.print(Text("  " + line, style="#7BD88F"))
        else:
            console.print(Text("  " + line, style="opus.muted"))
        shown += 1
    return f"{removed}x removida(s), {added}x acrescentada(s)"
