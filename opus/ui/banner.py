"""OPUS Agent - Banner de abertura.

Boot enxuto: mini logo em gradiente (3 linhas), uma linha de identidade
(modelo + workspace), separador fino e uma linha de dicas. Nada mais.
"""

from pathlib import Path
from rich.console import Console
from rich.text import Text

from .theme import get_theme, GLYPH_DOT

LOGO = [
    " ◢◣ ",
    "◣◤◢◤",
    " ◤◢ ",
]


def render_banner(console: Console, config: dict) -> None:
    """Mini logo em gradiente + identidade em uma linha + dica curta."""
    model = config.get("default_model", "?")
    workspace = Path.cwd().name or str(Path.cwd())
    theme_id = config.get("theme", "cyberpunk_neon")
    theme = get_theme(theme_id)

    logo = Text()
    logo.append(LOGO[0] + "\n", style=f"bold {theme['gradient'][0]}")
    logo.append(LOGO[1] + "   OPUS\n", style=f"bold {theme['gradient'][1]}")
    logo.append(LOGO[2], style=f"bold {theme['gradient'][2]}")
    console.print(logo)

    info = Text("   ")
    info.append(f"{model} ", style="bold " + theme["text"])
    info.append(f"{GLYPH_DOT} {workspace}", style="opus.muted")
    console.print(info)

    console.print("  " + "─" * 34, style="opus.muted")
    console.print(
        Text.assemble(
            ("  dica: ", "opus.muted"),
            ("/ajuda", "opus.accent"),
            (" lista comandos ", "opus.muted"),
            (GLYPH_DOT + " ", "opus.muted"),
            ("/sair", "opus.accent"),
            (" encerra", "opus.muted"),
        )
    )
    console.print()
