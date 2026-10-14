"""OPUS Agent - Comando /ajuda."""

from rich.console import Console
from rich.text import Text

COMMANDS = [
    ("/ajuda", "mostra esta lista"),
    ("/wizard", "abre a configuracao (provedor, chaves, tema)"),
    ("/tools", "lista ferramentas e MCPs"),
    ("/model", "troca provedor/modelo"),
    ("/raciocinio", "nivel de raciocinio (off/low/medium/high/max)"),
    ("/sessions", "lista sessoes"),
    ("/resume", "carrega sessao (numero ou id)"),
    ("/clear", "limpa a tela"),
    ("/sair", "encerra a sessao"),
]


def render_help(console: Console) -> None:
    console.print()
    for cmd, desc in COMMANDS:
        console.print(Text.assemble((f"  {cmd:<10}", "opus.accent"), (desc, "opus.muted")))
    console.print()
