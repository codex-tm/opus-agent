"""OPUS Agent - Buscar e ler pagina web (Playwright)."""

import json
import urllib.parse
import urllib.request


def _ddg(query: str, timeout: int = 15) -> list:
    """Busca do DuckDuckGo sem lib pesada."""
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    import re as re_mod
    return [
        {"url": u.replace("/l/?uddg=", "").split("?")[0], "title": t.strip()}
        for u, t in re_mod.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)', html)[:6]
    ]


def web_browse(url: str, acao: str = "ler", timeout: int = 20) -> str:
    """Navega/ler via Playwright sync. Retorna texto markdown-ish."""
    action = acao.lower()
    target_url = url or ""
    if action in ("buscar", "search") or not url.startswith(("http://", "https://")):
        query = url if url else acao
        return json.dumps({"ok": True, "results": _ddg(query)}, ensure_ascii=False)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(target_url, timeout=timeout * 1000, wait_until="domcontentloaded")
            title = page.title()
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            body = "\n".join(line.rstrip() for line in body.splitlines() if line.strip())[:6000]
            return json.dumps({"ok": True, "title": title, "text": body}, ensure_ascii=False)
        finally:
            browser.close()
