"""OPUS Agent - Markdown -> rich, streaming e snapshot.

Add sede: console limpa e re-renderiza a cada chunk. Formato fluido,
sem Panel, com thought em italic dim quando o modelo emite THINK:.
"""

import re

from rich.text import Text

_INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+?`)")
COLOR_TEXT = "#E6E6E6"
CODE_BG = "#1A1B26"
CODE_HEAD = "#8A8F98"


def md_to_lines(text: str) -> list:
    """Converte markdown em lista de ('code',...) | ('think',...) | ('md', text).

    Estrategia: linhas vazias dividem blocos. Blocos de fence (```) sao atomicos.
    Isso permite renderizar por bloco sem esperar o texto inteiro.
    """
    # separa o bloco de raciocinio embutido (THINK:...) se vier
    think_part, rest = "", text
    if "THINK:" in text:
        idx = text.index("THINK:")
        tail = text[idx + 6 :]
        j = tail.find("\n\n")
        if j >= 0:
            think_part = tail[:j]
            rest = text[:idx] + tail[j + 2 :]
        else:
            think_part, rest = tail, text[:idx]

    out = []
    if think_part and think_part.strip():
        out.append(("think", think_part.strip()))

    # fences sao blocos proprios; o resto split por linha
    lines = rest.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip() or "text"
            buf = []
            i += 1
            closed = False
            while i < len(lines):
                if lines[i].strip().startswith("```"):
                    closed = True
                    i += 1
                    break
                buf.append(lines[i])
                i += 1
            out.append(("code", lang, "\n".join(buf), closed))
            continue
        out.append(("md", line))
        i += 1
    return out


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE_I = re.compile(r"`([^`]+?)`")
_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def strip_markdown(text: str) -> str:
    """Remove marcadores markdown, deixando so o texto plano."""
    t = _FENCE.sub(lambda m: m.group(2), text)
    t = _BOLD.sub(r"\1", t)
    t = _CODE_I.sub(r"\1", t)
    return t


def _inline(text: str, base: str = "opus.text") -> Text:
    out = Text()
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            out.append(text[pos : m.start()], style=base)
        tok = m.group(0)
        if tok.startswith("**"):
            out.append(tok[2:-2], style="bold #E6E6E6")
        elif tok.startswith("`"):
            out.append(" " + tok[1:-1] + " ", style=f"#FFDF8E on {CODE_BG}")
        else:
            out.append(tok[1:-1], style=f"italic {COLOR_TEXT}")
        pos = m.end()
    if pos < len(text):
        out.append(text[pos:], style=base)
    return out


def render_blocks(console: "object", blocks: list) -> None:
    from rich.syntax import Syntax

    for kind, *data in blocks:
        if kind == "think":
            console.print(Text("  " + data[0].replace("\n", "\n  "), style="italic #8A8F98"))
        elif kind == "code":
            lang, code, closed = data
            console.print(Text(f"  {lang}", style=CODE_HEAD))
            console.print(
                Syntax(
                    code, lang, theme="one-dark", background_color=CODE_BG,
                    line_numbers=False, word_wrap=True, padding=(0, 1),
                )
            )
            console.print()
        else:
            line = data[0]
            stripped = line.strip()
            if stripped.startswith("## "):
                console.print(_inline(stripped[3:], base="bold #FF4FA3"))
            elif stripped.startswith("# "):
                console.print(_inline(stripped[2:], base="bold #FF4FA3"))
            elif stripped.startswith(("- ", "* ")):
                console.print(Text.assemble(("  \u2022 ", "opus.accent"), (_inline(stripped[2:]),)))
            elif stripped == "":
                console.print()
            else:
                console.print(_inline(stripped))


def render_markdown(console: "object", text: str) -> None:
    render_blocks(console, md_to_lines(text))
