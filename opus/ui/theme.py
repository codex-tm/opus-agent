"""OPUS Agent - Tema visual e tokens de design.

Dois niveis de cor apenas: acento (rosa/purpura) e esmaecido.
A regra da casa: o prompt do usuario e o UNICO elemento com cor forte;
tudo o resto e texto fluido ou linha dim.
"""

import sys
from rich.theme import Theme

# Paleta enxuta (gradiente roxo -> pink em 3 passos)
GRADIENT = ["#B18CFF", "#E06BBE", "#FF4FA3"]

COLOR_ACCENT = "#FF4FA3"      # rosa principal (prompt, glifos de acento)
COLOR_VIOLET = "#B18CFF"      # roxo suave (mini logo)
COLOR_TEXT = "#E6E6E6"        # texto normal
COLOR_MUTED = "#8A8F98"       # hints, metadados, separadores
COLOR_SUCCESS = "#7BD88F"
COLOR_WARNING = "#FFB454"
COLOR_ERROR = "#FF6B7A"

THEMES = {
    "cyberpunk_neon": {
        "name": "Cyberpunk Neon",
        "desc": "rosa/purpura sobre fundo escuro (padrao)",
        "gradient": ["#B18CFF", "#E06BBE", "#FF4FA3"],
        "accent": "#FF4FA3",
        "violet": "#B18CFF",
        "text": "#E6E6E6",
        "muted": "#8A8F98",
        "success": "#7BD88F",
        "warning": "#FFB454",
        "error": "#FF6B7A",
    },
    "dark_matrix": {
        "name": "Dark Matrix",
        "desc": "verde fosforo",
        "gradient": ["#00FF88", "#00CC6A", "#00AA55"],
        "accent": "#00FF88",
        "violet": "#00CC6A",
        "text": "#CCFFDD",
        "muted": "#66AA88",
        "success": "#00FF88",
        "warning": "#FFAA00",
        "error": "#FF4444",
    },
    "slate_obsidian": {
        "name": "Slate Obsidian",
        "desc": "cinza/azul minimalista",
        "gradient": ["#88AACC", "#6688AA", "#446688"],
        "accent": "#88AACC",
        "violet": "#6688AA",
        "text": "#DDDDDD",
        "muted": "#999999",
        "success": "#88CC88",
        "warning": "#FFAA66",
        "error": "#FF8888",
    },
    "sunset_horizon": {
        "name": "Sunset Horizon",
        "desc": "laranja/dourado",
        "gradient": ["#FF8844", "#FFBB33", "#FFDD00"],
        "accent": "#FF8844",
        "violet": "#FFBB33",
        "text": "#FFF8E8",
        "muted": "#CCAA88",
        "success": "#88CC88",
        "warning": "#FFDD44",
        "error": "#FF6666",
    },
}


def get_theme(theme_id: str = "cyberpunk_neon") -> dict:
    """Retorna configuracao do tema por ID."""
    return THEMES.get(theme_id, THEMES["cyberpunk_neon"])


def build_rich_theme(theme_id: str = "cyberpunk_neon") -> Theme:
    """Constrói Theme do Rich a partir do ID do tema."""
    t = get_theme(theme_id)
    return Theme({
        "opus.logo1": f"bold {t['gradient'][0]}",
        "opus.logo2": f"bold {t['gradient'][1]}",
        "opus.logo3": f"bold {t['gradient'][2]}",
        "opus.accent": f"bold {t['accent']}",
        "opus.text": t["text"],
        "opus.muted": t["muted"],
        "opus.success": t["success"],
        "opus.warning": t["warning"],
        "opus.error": t["error"],
    })


def clear_screen_full(console: "Console") -> None:
    """Limpa tela E scrollback buffer (escape sequence ANSI)."""
    # \033[H = cursor home, \033[2J = clear screen, \033[3J = clear scrollback
    console.file.write("\033[H\033[2J\033[3J")
    console.file.flush()


# Tema default (backward compat)
OPUS_THEME = build_rich_theme("cyberpunk_neon")

# Glifos
GLYPH_PROMPT = ">"
GLYPH_DOT = "."
GLYPH_WARN = "!"
GLYPH_CHECK = "+"
GLYPH_CROSS = "x"
