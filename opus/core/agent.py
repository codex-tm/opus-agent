"""
OPUS Agent - Loop do agente com tool calling; texto streama no fim.
Retry, circuit breaker, and resilience built-in.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import time
import random

from rich.text import Text

from .client import LLMError, chat, chat_stream
from .exec import execute_tool, tools_payload
from .tools import NATIVE_TOOLS
from ..ui.md_render import render_blocks, strip_markdown
from ..ui.tools_viewer import render_tool_execution

MAX_TURNS = 12

# Circuit breaker state per provider
_circuit_breakers: Dict[str, Dict[str, Any]] = {}


def _check_circuit_breaker(provider: str) -> bool:
    """Check if circuit breaker is open for provider."""
    cb = _circuit_breakers.get(provider, {})
    if cb.get("open", False):
        if time.time() - cb.get("opened_at", 0) > 60:  # 60s reset
            cb["open"] = False
            cb["failures"] = 0
            return False
        return True
    return False


def _record_failure(provider: str):
    """Record failure and potentially open circuit breaker."""
    cb = _circuit_breakers.setdefault(provider, {"failures": 0, "open": False, "opened_at": 0})
    cb["failures"] += 1
    if cb["failures"] >= 5:
        cb["open"] = True
        cb["opened_at"] = time.time()


def _record_success(provider: str):
    """Record success, reset failure count."""
    cb = _circuit_breakers.setdefault(provider, {"failures": 0, "open": False, "opened_at": 0})
    cb["failures"] = 0
    cb["open"] = False


def _chat_with_retry(config: dict, history: list, tools: list, max_retries: int = 3):
    """Chat with exponential backoff retry and circuit breaker."""
    provider = config.get("default_provider", "unknown")
    
    if _check_circuit_breaker(provider):
        raise LLMError(f"Circuit breaker open for {provider}")
    
    last_error = None
    for attempt in range(max_retries):
        try:
            result = chat(config, history, tools=tools if tools else None)
            _record_success(provider)
            return result
        except LLMError as e:
            last_error = e
            wait = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
    
    _record_failure(provider)
    raise last_error


def _stream_with_retry(config: dict, history: list, tools: list, console, max_retries: int = 3):
    """Stream with exponential backoff retry and circuit breaker."""
    provider = config.get("default_provider", "unknown")
    
    if _check_circuit_breaker(provider):
        raise LLMError(f"Circuit breaker open for {provider}")
    
    last_error = None
    for attempt in range(max_retries):
        try:
            yield from chat_stream(config, history, tools=tools if tools else None)
            _record_success(provider)
            return
        except LLMError as e:
            last_error = e
            wait = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
    
    _record_failure(provider)
    raise last_error


def run_agent(console, config, history, ask_callback, cwd=None):
    """Loop principal. Retorna texto final (markdown) do assistente."""
    cwd = Path(cwd) if cwd else Path.cwd()
    ids = [t["id"] for t in NATIVE_TOOLS]
    payload_tools = tools_payload(ids, config)
    is_tty = getattr(console, "is_terminal", False)

    def _stream_or_chat():
        """TTY: spinner ate primeiro token; nao-TTY: chat bloqueado com spinner."""
        if not is_tty:
            result = _chat_with_retry(config, history, payload_tools)
            if result.reasoning:
                render_blocks(console, [("think", result.reasoning)])
            return result.content, result.tool_calls

        spinner = console.status("  pensando...", spinner="dots", spinner_style="opus.accent")
        spinner.start()
        content, tool_calls = [], []
        try:
            for kind, data in _stream_with_retry(config, history, payload_tools, console):
                if kind == "think":
                    spinner.stop()
                    render_blocks(console, [("think", data)])
                    spinner.start()
                elif kind == "text":
                    spinner.stop()
                    content.append(data)
                    console.file.write(strip_markdown(data))
                    console.file.flush()
                elif kind == "toolcall":
                    tool_calls.append(data)
        finally:
            spinner.stop()
        if content:
            console.file.write("\n")
            console.file.flush()
        return "".join(content), tool_calls

    for _turn in range(MAX_TURNS):
        try:
            content, tool_calls = _stream_or_chat()
        except LLMError as e:
            return None, f"erro: {e}"

        if not tool_calls:
            if content:
                history.append({"role": "assistant", "content": content})
            return content, None

        history.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})

        for call in tool_calls:
            fn = call.get("function", {})
            tid = fn.get("name", "")
            import json as _json
            try:
                args = _json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}

            if tid == "ask_user":
                question = args.get("question", "O agente pediu esclarecimento.")
                answer = ask_callback(question)
                history.append({
                    "role": "tool", "tool_call_id": call.get("id", ""),
                    "name": tid, "content": str(answer),
                })
                continue

            auto = config.get("auto_approve_tools", False)
            needs = tid in ("write_file", "edit_file", "execute_command", "web_search")
            approved = True
            if needs and not auto:
                approved = bool(ask_callback(f"executar {tid}? [s/N]", confirm=True))
            if not approved:
                output = "negado pelo usuario"
            else:
                try:
                    output = execute_tool(tid, args, cwd, config)
                except PermissionError as e:
                    output = f"erro: {e}"
                except Exception as e:
                    output = f"erro: {e}"

            # Professional tool execution display
            try:
                data = _json.loads(output)
                render_tool_execution(console, tid, args, data, config)
            except Exception:
                # Fallback for non-JSON output
                console.print(Text(f"  {tid}: {str(output)[:200]}", style="#B0B0B0"))

            history.append({
                "role": "tool", "tool_call_id": call.get("id", ""),
                "name": tid, "content": output,
            })

    return None, "limite de passos atingido"
