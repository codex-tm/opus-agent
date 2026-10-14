"""OPUS Agent - Wizard de configuracao (layout limpo, sem cards coloridos)."""

import sys
import time
from typing import Any, Dict

from rich.console import Console
from rich.prompt import Confirm

from .prompt_input import pipe_read, is_interactive_tty

from rich.table import Table
from rich.text import Text

from ..config import save_config
from ..core.models import fetch_models
from .help_view import COMMANDS  # noqa: F401  (reuso futuro)
from .select import select
from .theme import GLYPH_CHECK, GLYPH_CROSS, GLYPH_DOT, clear_screen_full

PROVIDERS = [
    ("anthropic", "Anthropic Claude", "claude-3-5-sonnet-20241022", "recomendado para codigo"),
    ("openai", "OpenAI", "gpt-4o", "raciocinio geral"),
    ("google", "Google Gemini", "gemini-2.0-flash", "janela de contexto grande"),
    ("ollama", "Ollama (local)", "llama3.1:latest", "offline e privado"),
    ("deepseek", "DeepSeek", "deepseek-coder", "bom custo para codigo"),
    ("groq", "Groq", "llama-3.3-70b-versatile", "inferencia rapida"),
    ("custom", "Custom (URL propria)", "", "proxy / endpoint OpenAI-compat qualquer"),
]

THEMES = [
    ("cyberpunk_neon", "Cyberpunk Neon", "rosa/purpura sobre fundo escuro (padrao)"),
    ("dark_matrix", "Dark Matrix", "verde fosforo"),
    ("slate_obsidian", "Slate Obsidian", "cinza/azul minimalista"),
    ("sunset_horizon", "Sunset Horizon", "laranja/dourado"),
]

ENV_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def mask_api_key(key: str) -> str:
    if not key:
        return "(vazia)"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


class OpusWizard:
    def __init__(self, console: Console, config: Dict[str, Any]):
        self.console = console
        self.config = config
        self._finished = False

    # ---- loop principal ----

    def run(self) -> Dict[str, Any]:
        while True:
            clear_screen_full(self.console)
            self._render_header()
            self._render_status()
            choice = self._render_menu()

            if choice == "1":
                self._flow_provider()
            elif choice == "2":
                self._menu_reasoning()
            elif choice == "3":
                            self._menu_security_step()
            elif choice == "0":
                save_config(self.config)
                self._toast("configuracoes salvas")
                time.sleep(0.6)
                break
            else:
                self.console.print(Text("  opcao invalida", style="opus.error"))
                time.sleep(0.8)
        return self.config

    # ---- render ----

    def _render_header(self) -> None:
        self.console.print()
        self.console.print(Text("  opus / configuracao", style="opus.accent"))
        self.console.print(
            Text(
                "  provedor, seguranca e tema.",
                style="opus.muted",
            )
        )
        self.console.print()

    def _render_status(self) -> None:
        provider = self.config.get("default_provider", "?")
        model = self.config.get("default_model", "?")
        key = self.config.get("api_keys", {}).get(provider, "")
        auto = self.config.get("auto_approve_tools", False)
        theme = self.config.get("theme", "cyberpunk_neon")
        base_url = (self.config.get("endpoints", {}) or {}).get(provider, {}) or {}
        base_url = base_url.get("base_url", "")

        key_str = "ok" if key else "ausente"
        mode_str = "livre" if auto else "seguro"

        line = Text("  ")
        line.append(f"{provider}/{model}", style="bold #E6E6E6")
        line.append(f"  {GLYPH_DOT} chave: {key_str} ", style="opus.muted")
        line.append(f"{GLYPH_DOT} modo: {mode_str} ", style="opus.muted")
        line.append(f"{GLYPH_DOT} tema: {theme}", style="opus.muted")
        if base_url and provider == "custom":
            line.append(f" {GLYPH_DOT} {base_url}", style="opus.muted")
        self.console.print(line)
        self.console.print()

    def _render_menu(self) -> str:
        items = [
            ("1", "provedor e modelo"),
            ("2", "raciocinio (nivel)"),
            ("3", "seguranca (auto-aprovacao)"),
            ("0", "salvar e voltar"),
        ]
        picked = select(
            self.console,
            "configuracao",
            [(desc, "") for _, desc in items],
        )
        for num, desc in items:
            if picked == num:
                return num
        if picked.isdigit():
            idx = int(picked) - 1
            if 0 <= idx < len(items):
                return items[idx][0]
        return "0"

    # ---- submenus ----

    def menu_provider_and_model(self) -> None:
        clear_screen_full(self.console)
        self.console.print()
        self.console.print(Text("  provedor e modelo", style="opus.accent"))
        self.console.print()

        choice = select(
            self.console,
            "provedor e modelo",
            [
                (
                    f"{GLYPH_CHECK if self.config.get('default_provider') == pid else ' '} {name}",
                    f"{model}  {desc}",
                )
                for (pid, name, model, desc) in PROVIDERS
            ],
        )
        if choice.isdigit() and 1 <= int(choice) <= len(PROVIDERS):
            pid, name, model, _ = PROVIDERS[int(choice) - 1]
            if pid == "custom":
                self._menu_custom_provider()
                self._finished = True
                return
            self.config["default_provider"] = pid
            custom = pipe_read(f"modelo para {name}", model)
            self.config["default_model"] = custom
            save_config(self.config)
            self._toast(f"provedor: {name} ({custom})")
            time.sleep(0.8)

    def _flow_provider(self) -> None:
        """Fluxo completo: provedor+modelo -> seguranca -> tema -> salva."""
        self._finished = False
        self.menu_provider_and_model()
        if self._finished:
            return
        self._menu_security_step()
        self._menu_theme_step()
        save_config(self.config)
        self._toast("configuracao salva")
        time.sleep(0.8)

    def _menu_security_step(self) -> None:
        clear_screen_full(self.console)
        self.console.print()
        self.console.print(Text("  seguranca", style="opus.accent"))
        current = self.config.get("auto_approve_tools", False)
        state = "livre (sem confirmacao)" if current else "seguro (confirma cada acao)"
        self.console.print(Text.assemble(("  modo atual: ", "opus.muted"), (state, "bold #E6E6E6")))
        resp = pipe_read("alternar o modo? [s/N]") if not is_interactive_tty() else ""
        toggle = (resp.lower() == "s") if not is_interactive_tty() else Confirm.ask("  alternar o modo?", default=False, console=self.console)
        if toggle:
            self.config["auto_approve_tools"] = not current

    def _menu_theme_step(self) -> None:
        clear_screen_full(self.console)
        self.console.print()
        self.console.print(Text("  tema visual", style="opus.accent"))
        choice = select(
            self.console,
            "tema visual",
            [
                (
                    f"{GLYPH_CHECK if self.config.get('theme') == tid else ' '} {name}",
                    desc,
                )
                for (tid, name, desc) in THEMES
            ],
        )
        if choice.isdigit() and 1 <= int(choice) <= len(THEMES):
            self.config["theme"] = THEMES[int(choice) - 1][0]
            save_config(self.config)

    def _menu_reasoning(self) -> None:
        """Nivel de raciocinio (reasoning_effort)."""
        clear_screen_full(self.console)
        self.console.print()
        self.console.print(Text("  nivel de raciocinio", style="opus.accent"))
        self.console.print()

        provider = self.config.get("default_provider", "")
        endpoints = self.config.get("endpoints", {}) or {}
        base_url = (endpoints.get(provider, {}) or {}).get("base_url", "")
        api_key = (self.config.get("api_keys", {}) or {}).get(provider, "")

        levels = ["off", "low", "medium", "high", "max"]
        support = {"supported": True, "levels": levels}
        if base_url:
            from ..core.models import detect_reasoning_support
            try:
                sup = detect_reasoning_support(base_url, api_key)
                if sup.get("levels"):
                    levels = sup["levels"]
            except Exception:
                pass

        options = ["off"] + [lv for lv in ["low", "medium", "high", "max"] if lv in levels]
        cur = self.config.get("reasoning", "medium")
        choice = select(
            self.console,
            "nivel de raciocinio",
            [(f"{GLYPH_CHECK if lv == cur else ' '} {lv}", "") for lv in options],
        )
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            self.config["reasoning"] = options[int(choice) - 1]
            save_config(self.config)
            self._toast(f"raciocinio: {self.config['reasoning']}")
            time.sleep(0.6)

    def _menu_custom_provider(self) -> None:
        """Endpoint OpenAI-compat custom: base URL, chave opcional, fetch de /models."""
        clear_screen_full(self.console)
        self.console.print()
        self.console.print(Text("  endpoint custom (OpenAI-compat)", style="opus.accent"))
        self.console.print()

        endpoints = self.config.setdefault("endpoints", {})
        cur = endpoints.get("custom", {}) or {}

        base_url = pipe_read("base URL (ex: http://localhost:8080/v1)", cur.get("base_url", ""))
        if not base_url:
            return

        api_key = pipe_read("API key (opcional, Enter pula)")

        endpoints["custom"] = {
            "name": "Custom",
            "base_url": base_url,
            "default_model": cur.get("default_model", ""),
            "enabled": True,
        }
        if api_key:
            self.config.setdefault("api_keys", {})["custom"] = api_key
        self.config["default_provider"] = "custom"

        self.console.print(Text("  consultando /models...", style="opus.muted"))
        try:
            models = fetch_models(base_url, api_key)
        except Exception as e:
            models = []
            self.console.print(Text(f"  nao consegui listar ({e})", style="opus.warning"))

        chosen = ""
        if models:
            items = [(m, "") for m in models] + [("digitar id manualmente...", "")]
            choice = select(self.console, "modelos disponiveis", items)
            if choice.isdigit() and 1 <= int(choice) <= len(models):
                chosen = models[int(choice) - 1]
            elif choice.isdigit() and int(choice) == len(models) + 1:
                chosen = pipe_read("id do modelo")
        if not chosen:
            chosen = pipe_read("id do modelo", cur.get("default_model", ""))

        self.config["default_model"] = chosen
        endpoints["custom"]["default_model"] = chosen
        save_config(self.config)
        self._toast(f"custom: {base_url} ({chosen})")
        time.sleep(0.8)


    def _toast(self, message: str) -> None:
        self.console.print(
            Text.assemble((f"  {GLYPH_CHECK} ", "opus.success"), (message, "opus.text"))
        )
