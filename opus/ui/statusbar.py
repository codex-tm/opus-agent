"""OPUS Agent - Barra de status fina (1 linha)."""

from pathlib import Path
from rich.console import Console
from rich.text import Text

from .theme import get_theme, GLYPH_DOT


def render_statusbar(console: Console, config: dict) -> None:
    provider = config.get("default_provider", "?")
    model = config.get("default_model", "?")
    workspace = Path.cwd().name or str(Path.cwd())
    safe = "livre" if config.get("auto_approve_tools") else "seguro"
    reasoning = config.get("reasoning", "medium")
    think = f"raciocinio {reasoning}" if reasoning and reasoning != "off" else "sem raciocinio"

    bar = Text(" ")
    bar.append(f" {workspace} ", style="opus.muted")
    bar.append(f"{GLYPH_DOT} ", style="opus.muted")
    bar.append(f"{provider}/{model} ", style="opus.muted")
    bar.append(f"{GLYPH_DOT} ", style="opus.muted")
    bar.append(f"{think} ", style="opus.muted")
    bar.append(f"{GLYPH_DOT} ", style="opus.muted")
    bar.append(safe, style="opus.muted")
    console.print(bar)
