"""
OPUS Agent - Professional Tools Dashboard UI.

Rich, professional display with tables, panels, and proper formatting.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.align import Align
from rich.box import ROUNDED, MINIMAL

from .theme import get_theme, GLYPH_WARN, GLYPH_CHECK
from ..core.tools import get_all_tools, TOOL_CATEGORIES


def render_tools_dashboard(console: Console, config: dict) -> None:
    """Render professional tools dashboard with tables and panels."""
    tools = get_all_tools(config)
    theme_id = config.get("theme", "cyberpunk_neon")
    theme = get_theme(theme_id)

    # Categorize tools
    categorized: dict = {}
    for t in tools:
        categorized.setdefault(t["category"], []).append(t)

    console.print()

    # Header panel
    total_tools = len(tools)
    native_count = sum(1 for t in tools if not t["id"].startswith("mcp_"))
    mcp_count = total_tools - native_count

    header_text = Text()
    header_text.append("FERRAMENTAS DISPONÍVEIS", style=f"bold {theme['accent']}")
    header_text.append(f"  ({total_tools} total: {native_count} nativas", style=theme["muted"])
    if mcp_count:
        header_text.append(f", {mcp_count} MCP", style=theme["muted"])
    header_text.append(")", style=theme["muted"])

    console.print(Panel(
        Align.center(header_text),
        style=theme["accent"],
        border_style=theme["accent"],
        box=ROUNDED,
        padding=(0, 1),
    ))
    console.print()

    # Render each category as a table
    for cat_key, cat_tools in categorized.items():
        title = TOOL_CATEGORIES.get(cat_key, cat_key.upper())

        # Create table for this category
        table = Table(
            title=f"[bold {theme['accent']}]{title}[/]",
            title_style=theme["accent"],
            box=MINIMAL,
            show_header=True,
            header_style=f"bold {theme['text']}",
            border_style=theme["muted"],
            padding=(0, 1),
            expand=False,
        )

        table.add_column("Ferramenta", style=f"bold {theme['text']}", width=30, no_wrap=True)
        table.add_column("Descrição", style=theme["muted"], width=70)
        table.add_column("", justify="center", width=4)

        for tool in cat_tools:
            name = tool["id"]
            desc = tool["description"]
            danger = tool.get("dangerous", False)

            # Truncate description if too long
            if len(desc) > 68:
                desc = desc[:65] + "..."

            danger_mark = f"[{theme['warning']}]{GLYPH_WARN}[/]" if danger else ""

            table.add_row(name, desc, danger_mark)

        console.print(table)
        console.print()

    # Legend panel
    legend_items = []
    legend_items.append(Text.assemble(
        (f" {GLYPH_WARN} ", f"bold {theme['warning']}"),
        ("Requer confirmação antes de executar", theme["muted"]),
    ))
    if config.get("auto_approve_tools"):
        legend_items.append(Text.assemble(
            (f" {GLYPH_CHECK} ", f"bold {theme['success']}"),
            ("Modo livre ativo - confirmação desabilitada", theme["muted"]),
        ))
    else:
        legend_items.append(Text.assemble(
            (f" {GLYPH_CHECK} ", f"bold {theme['muted']}"),
            ("Modo seguro ativo - confirmação necessária", theme["muted"]),
        ))

    legend_content = Columns(legend_items, equal=True, expand=True)
    console.print(Panel(
        legend_content,
        title=f"[bold {theme['accent']}]LEGENDA[/]",
        border_style=theme["muted"],
        box=ROUNDED,
        padding=(0, 2),
    ))
    console.print()


def render_tool_execution(console: Console, tool_name: str, args: dict, result: dict, config: dict) -> None:
    """Render tool execution with professional formatting."""
    theme_id = config.get("theme", "cyberpunk_neon")
    theme = get_theme(theme_id)

    is_mcp = tool_name.startswith("mcp_")
    prefix = "MCP" if is_mcp else "TOOL"

    # Build status
    ok = result.get("ok", False)
    status_color = theme["success"] if ok else theme["error"]
    status_icon = GLYPH_CHECK if ok else GLYPH_WARN
    status_text = "SUCESSO" if ok else "ERRO"

    # Header
    header = Text()
    header.append(f"{prefix}: ", style=f"bold {theme['accent']}")
    header.append(tool_name, style=f"bold {theme['text']}")
    header.append(f"  [{status_icon} {status_text}]", style=f"bold {status_color}")

    console.print()
    console.print(Panel(
        header,
        border_style=status_color,
        box=ROUNDED,
        padding=(0, 1),
    ))

    # Arguments
    if args:
        args_text = Text()
        args_text.append("Argumentos:\n", style=f"bold {theme['muted']}")
        for k, v in args.items():
            val = str(v)
            if len(val) > 80:
                val = val[:77] + "..."
            args_text.append(f"  {k}: ", style=theme["text"])
            args_text.append(f"{val}\n", style=theme["muted"])

        console.print(Panel(
            args_text,
            title=f"[bold {theme['accent']}]ARGUMENTOS[/]",
            border_style=theme["muted"],
            box=MINIMAL,
            padding=(0, 1),
        ))

    # Result
    if ok:
        result_text = Text()
        if "result" in result:
            res = result["result"]
            if isinstance(res, dict):
                for k, v in res.items():
                    val = str(v)
                    if len(val) > 100:
                        val = val[:97] + "..."
                    result_text.append(f"  {k}: ", style=theme["text"])
                    result_text.append(f"{val}\n", style=theme["muted"])
            else:
                val = str(res)
                if len(val) > 200:
                    val = val[:197] + "..."
                result_text.append(f"  {val}", style=theme["muted"])
        else:
            result_text.append("  (sem detalhes)", style=theme["muted"])

        console.print(Panel(
            result_text,
            title=f"[bold {theme['success']}]RESULTADO[/]",
            border_style=theme["success"],
            box=MINIMAL,
            padding=(0, 1),
        ))
    else:
        error = result.get("error", "Erro desconhecido")
        console.print(Panel(
            Text(f"  {error}", style=theme["error"]),
            title=f"[bold {theme['error']}]ERRO[/]",
            border_style=theme["error"],
            box=MINIMAL,
            padding=(0, 1),
        ))

    console.print()
