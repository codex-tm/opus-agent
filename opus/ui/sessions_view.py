"""OPUS Agent - /sessions: lista numerada, limpa, sem poluicao."""

from rich.console import Console
from rich.text import Text

from ..core.session_store import SessionStore


def render_sessions(console: Console, store: SessionStore, current_id: str) -> None:
    rows = store.list_sessions()
    console.print()
    if not rows:
        console.print(Text("  nenhuma sessao ainda.", style="opus.muted"))
        console.print()
        return
    for idx, s in enumerate(rows, 1):
        mark = "●" if s["id"] == current_id else " "
        console.print(
            Text.assemble(
                (f"  {idx:<3}", "opus.accent"),
                (f"{mark} ", "opus.success" if s["id"] == current_id else "opus.muted"),
                (f"{s['id']:<8}", "bold #E6E6E6"),
                ((s["name"] or "(sem nome)"), "opus.muted"),
            )
        )
    console.print()
