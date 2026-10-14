"""OPUS Agent - Cliente LLM minimo (OpenAI-compat + Anthropic), stdlib."""

import json
import urllib.error
import urllib.request

OPENAI_COMPAT = {"openai", "deepseek", "groq", "ollama", "openrouter", "custom"}

DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "ollama": "http://localhost:11434/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "anthropic": "https://api.anthropic.com/v1",
}

# Anthropic API version
ANTHROPIC_VERSION = "2023-06-01"


class LLMError(Exception):
    pass


class LLMDone:
    """Result completo do chat (content + reasoning + tool_calls montados)."""

    def __init__(self, content: str = "", tool_calls: "list | None" = None, reasoning: str = ""):
        self.content = content or ""
        self.reasoning = reasoning or ""
        self.tool_calls = tool_calls or []

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


def _post(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise LLMError(f"falha de conexao: {e.reason}")


def _chat_payload(config: dict, messages: list, tools: "list | None", stream: bool) -> "tuple[str, dict, dict]":
    provider = config.get("default_provider", "openai")
    model = config.get("default_model", "gpt-4o")
    api_key = (config.get("api_keys", {}) or {}).get(provider, "")
    base_url = ((config.get("endpoints", {}) or {}).get(provider, {}) or {}).get(
        "base_url"
    ) or DEFAULT_URLS.get(provider, "")
    if not base_url:
        raise LLMError(f"sem base URL para '{provider}' (configure em /wizard)")
    if not api_key and provider not in ("ollama", "custom"):
        raise LLMError(f"sem chave de API para '{provider}' (configure em /wizard)")
    level = config.get("reasoning", "medium")
    if provider == "anthropic":
        return _anthropic_payload(config, messages, tools, stream)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if stream:
        payload["stream"] = True
    if level and level != "off":
        payload["reasoning_effort"] = _sanitize_reasoning_level(level)
    return base_url.rstrip("/") + "/chat/completions", headers, payload


def _anthropic_payload(config: dict, messages: list, tools: "list | None", stream: bool) -> "tuple[str, dict, dict]":
    provider = config.get("default_provider", "openai")
    model = config.get("default_model", "claude-3-5-sonnet-20241022")
    api_key = (config.get("api_keys", {}) or {}).get(provider, "")
    base_url = ((config.get("endpoints", {}) or {}).get(provider, {}) or {}).get(
        "base_url"
    ) or DEFAULT_URLS.get(provider, "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    # Anthropic uses system param separate from messages
    system_msgs = [m for m in messages if m["role"] == "system"]
    user_msgs = [m for m in messages if m["role"] != "system"]
    system = system_msgs[0]["content"] if system_msgs else ""
    payload = {"model": model, "messages": user_msgs, "max_tokens": 4096}
    if system:
        payload["system"] = system
    if tools:
        # Convert OpenAI tools to Anthropic format
        anthro_tools = []
        for t in tools:
            fn = t.get("function", {})
            anthro_tools.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        payload["tools"] = anthro_tools
    if stream:
        payload["stream"] = True
    return base_url.rstrip("/") + "/messages", headers, payload


def _stream_anthropic(config: dict, messages: list, tools: "list | None"):
    url, headers, payload = _anthropic_payload(config, messages, tools, stream=True)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    tcs: dict = {}
    current_tool_use = None
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                line = line[5:].strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = chunk.get("type", "")
                if event_type == "message_start":
                    continue
                elif event_type == "content_block_start":
                    block = chunk.get("content_block", {})
                    if block.get("type") == "tool_use":
                        current_tool_use = {
                            "id": block.get("id", f"c{len(tcs)}"),
                            "name": block.get("name"),
                            "arguments": ""
                        }
                        tcs[block.get("index", len(tcs))] = current_tool_use
                elif event_type == "content_block_delta":
                    delta = chunk.get("delta", {})
                    if delta.get("type") == "text":
                        yield ("text", delta.get("text", ""))
                    elif delta.get("type") == "input_json":
                        if current_tool_use:
                            current_tool_use["arguments"] += delta.get("partial_json", "")
                elif event_type == "content_block_stop":
                    current_tool_use = None
                elif event_type == "message_delta":
                    pass
                elif event_type == "message_stop":
                    break
        for idx in sorted(tcs):
            t = tcs[idx]
            yield ("toolcall", {
                "id": t["id"],
                "type": "function",
                "function": {"name": t["name"], "arguments": t["arguments"]},
            })
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise LLMError(f"falha de conexao: {e.reason}")


def _chat_anthropic(config: dict, messages: list, tools: "list | None") -> LLMDone:
    url, headers, payload = _anthropic_payload(config, messages, tools, stream=False)
    data = _post(url, headers, payload)
    # Anthropic response format
    content = ""
    tool_calls = []
    reasoning = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            content += block.get("text", "")
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name"),
                    "arguments": json.dumps(block.get("input", {}))
                }
            })
        elif block.get("type") == "thinking":
            reasoning += block.get("thinking", "")
    return LLMDone(content, tool_calls, reasoning)


_LEVELS_COERCE = {"minimal": "low", "max": "high", "xhigh": "high"}
_VALID_LEVELS = ("low", "medium", "high")


def _sanitize_reasoning_level(level: str) -> str:
    """Coerce niveis nao suportados pela API (max, minimal) para o padrao."""
    lv = _LEVELS_COERCE.get(level, level)
    return lv if lv in _VALID_LEVELS else "medium"


def chat(config: dict, messages: list, tools: "list | None" = None) -> LLMDone:
    """Uma rodada completa (nao-stream)."""
    provider = config.get("default_provider", "openai")
    if provider == "anthropic":
        return _chat_anthropic(config, messages, tools)
    url, headers, payload = _chat_payload(config, messages, tools, stream=False)
    data = _post(url, headers, payload)
    msg = data["choices"][0]["message"]
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    return LLMDone(msg.get("content") or "", msg.get("tool_calls") or [], reasoning)


def _stream_openai(config: dict, messages: list, tools: "list | None"):
    url, headers, payload = _chat_payload(config, messages, tools, stream=True)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    tcs: dict = {}
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                think = delta.get("reasoning_content") or delta.get("reasoning") or ""
                if think:
                    yield ("think", think)
                piece = delta.get("content", "")
                if piece:
                    yield ("text", piece)
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    fn = tc.get("function") or {}
                    if "name" in fn:
                        tcs.setdefault(idx, {"id": tc.get("id", f"c{idx}"), "name": fn["name"], "arguments": ""})
                    if "arguments" in fn and idx in tcs:
                        tcs[idx]["arguments"] += fn["arguments"]
        for idx in sorted(tcs):
            t = tcs[idx]
            yield ("toolcall", {
                "id": t["id"],
                "type": "function",
                "function": {"name": t["name"], "arguments": t["arguments"]},
            })
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise LLMError(f"falha de conexao: {e.reason}")


def chat_stream(config: dict, messages: list, tools: "list | None" = None):
    """Stream de texto (+ reasoning). Tools so felpas no primeiro delta."""
    provider = config.get("default_provider", "openai")
    if provider in OPENAI_COMPAT:
        yield from _stream_openai(config, messages, tools)
        return
    if provider == "anthropic":
        yield from _stream_anthropic(config, messages, tools)
        return
    result = chat(config, messages, tools)
    if result.reasoning:
        yield ("think", result.reasoning)
    if result.content:
        yield ("text", result.content)
    for tc in result.tool_calls:
        yield ("toolcall", tc)
