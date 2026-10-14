"""OPUS Agent - Busca modelos de um endpoint OpenAI-compat (/models)."""

import json
import urllib.request


def fetch_models(base_url: str, api_key: str = "", timeout: int = 10) -> list:
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
    return sorted(set(ids))


def detect_reasoning_support(base_url: str, api_key: str, timeout: int = 10) -> dict:
    """Consulta /models e infere suporte a reasoning por nome de modelo."""
    try:
        ids = fetch_models(base_url, api_key, timeout)
    except Exception:
        return {"supported": False, "levels": [], "model_names": [], "param": "reasoning_effort"}
    names = [m.lower() for m in ids]
    has_gpt5 = any("gpt-5" in n for n in names)
    has_claude37 = any("3-7" in n or "sonnet-4" in n for n in names)
    has_dsr1 = any("deepseek-r1" in n or "deepseek-reasoner" in n for n in names)
    has_o = any(n.startswith("o1") or n.startswith("o3") for n in names)
    levels = []
    if has_gpt5 or has_claude37:
        levels = ["low", "medium", "high", "max"]
    elif has_dsr1 or has_o:
        levels = ["low", "medium", "high"]
    return {
        "supported": bool(levels),
        "levels": levels,
        "model_names": ids,
        "param": "reasoning_effort",
    }
