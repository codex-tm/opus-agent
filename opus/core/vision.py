"""OPUS Agent - Visao: clipboard (Ctrl+V) ou caminho, base64 pra API."""

import base64
import mimetypes
import sys
from pathlib import Path

from ..ui.prompt_input import pipe_read

# modelos que a gente sabe que tem visao
VISION_OK = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4.1",
    "claude-3", "claude-3-5", "claude-3-7", "claude-sonnet",
    "gemini-1.5", "gemini-2", "gemini-2.0",
    "llava", "llama3.2-vision", "qwen-vl", "qwen2-vl", "qwen2.5-vl",
}


def has_vision_support(model: str) -> bool:
    m = (model or "").lower()
    return any(k in m for k in VISION_OK)


def read_image(source: str) -> "tuple[bytes, str] | None":
    """Le imagem de caminho ou do clipboard. Retorna (bytes, mime)."""
    source = (source or "").strip().strip('"')
    if source and Path(source).exists():
        mime, _ = mimetypes.guess_type(source)
        return Path(source).read_bytes(), (mime or "image/png")

    # tenta o clipboard (Ctrl+V)
    if source in ("", "clipboard"):
        if not sys.platform.startswith("win"):
            return None
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                return None
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
        except Exception:
            return None
    return None


def image_to_data_url(b: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(b).decode("ascii")


def build_message(prompt_text: str, b: bytes, mime: str) -> dict:
    """Mensagem multimodal OpenAI-compat."""
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt_text or "Analise esta imagem."},
            {"type": "image_url", "image_url": {"url": image_to_data_url(b, mime)}},
        ],
    }
