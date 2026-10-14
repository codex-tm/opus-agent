"""
OPUS Agent - Execucao real das tools nativas (cwd = projeto atual) + MCP.
"""

import ast
import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional

from ..mcp_client import MCPClientManager, load_mcp_config


# Global MCP client manager (initialized once per session)
_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_manager(config: dict) -> MCPClientManager:
    """Get or create MCP client manager for this session."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
        # Load MCP servers from config
        from ..config_v2 import CONFIG_DIR
        mcp_config_path = CONFIG_DIR / "config.toml"
        servers = load_mcp_config(mcp_config_path)
        for server_id, server_config in servers.items():
            _mcp_manager.register(server_config)
        _mcp_manager.start_all()
    return _mcp_manager


def web_search(query: str, timeout: int = 12) -> str:
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    import re as re_mod
    links = re_mod.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)', html)
    items = [{"title": t.strip(), "url": u.replace("/l/?uddg=", "").split("?")[0]} for u, t in links[:8]]
    return json.dumps({"ok": True, "results": items}, ensure_ascii=False)


def _resolve(cwd: Path, filepath: str) -> Path:
    """Resolve filepath DENTRO do cwd; nega fora do projeto."""
    p = Path(filepath)
    if not p.is_absolute():
        p = Path(cwd) / p
    p = p.resolve()
    try:
        p.relative_to(Path(cwd).resolve())
    except ValueError:
        raise PermissionError(f"fora do workspace: {filepath}")
    return p


def execute_tool(tid: str, args: dict, cwd: Path, config: dict) -> str:
    """Executa e retorna string JSON (pronta pra tool_result)."""
    
    # Handle MCP tools (mcp_*)
    if tid.startswith("mcp_"):
        manager = get_mcp_manager(config)
        # Extract server_id and tool_name from mcp_{server_id}_{tool_name}
        parts = tid.split("_", 2)
        if len(parts) >= 3:
            server_id = parts[1]
            tool_name = parts[2]
        else:
            server_id = parts[1] if len(parts) == 2 else "filesystem"
            tool_name = args.get("tool_name", "")
        
        if not tool_name:
            return json.dumps({"ok": False, "error": "tool_name required for MCP tools"}, ensure_ascii=False)
        
        result = manager.call_tool(server_id, tool_name, args.get("arguments", args))
        return json.dumps(result, ensure_ascii=False)
    
    if tid == "read_file":
        path = _resolve(cwd, args["filepath"])
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(args.get("start_line", 1) or 1))
        end = min(len(lines), int(args.get("end_line", len(lines)) or len(lines)))
        sel = lines[start - 1 : end]
        return json.dumps({
            "ok": True,
            "path": str(path),
            "lines": sel,
            "truncated": end < len(lines),
        }, ensure_ascii=False)

    if tid == "write_file":
        path = _resolve(cwd, args["filepath"])
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        new = args.get("content", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")
        return json.dumps({"ok": True, "path": str(path), "old": old, "new": new}, ensure_ascii=False)

    if tid == "edit_file":
        path = _resolve(cwd, args["filepath"])
        old = path.read_text(encoding="utf-8", errors="replace")
        target, repl = args.get("target_block", ""), args.get("replacement_block", "")
        if target not in old:
            return json.dumps({"ok": False, "error": "bloco nao encontrado"}, ensure_ascii=False)
        new = old.replace(target, repl, 1)
        path.write_text(new, encoding="utf-8")
        return json.dumps({"ok": True, "path": str(path), "old": old, "new": new}, ensure_ascii=False)

    if tid == "list_files":
        base = Path(cwd)
        depth = int(args.get("depth", 3) or 3)
        skip = {".git", ".venv", "node_modules", "__pycache__"}
        out = []
        def walk(p: Path, d: int):
            if d > depth or len(out) >= 300:
                return
            try:
                entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return
            for e in entries:
                if e.name in skip:
                    continue
                rel = str(e.relative_to(base))
                out.append(rel + ("/" if e.is_dir() else ""))
                if e.is_dir():
                    walk(e, d + 1)
        walk(base, 1)
        return json.dumps({"ok": True, "files": out, "truncated": len(out) >= 300}, ensure_ascii=False)

    if tid == "search_code":
        import re as re_mod
        base = Path(cwd)
        pattern = args["query"]
        case = bool(args.get("case_sensitive"))
        flags = 0 if case else re_mod.IGNORECASE
        exts = tuple(x.lstrip(".") for x in (args.get("file_types") or [])) or None
        matches = []
        for path in base.rglob("*"):
            if not path.is_file() or any(s in path.parts for s in (".git", ".venv", "node_modules", "__pycache__")):
                continue
            if exts and path.suffix.lstrip(".") not in exts:
                continue
            try:
                for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if re_mod.search(pattern, line, flags):
                        matches.append({"file": str(path.relative_to(base)), "line": i, "text": line.strip()})
                        if len(matches) >= 50:
                            raise StopIteration
            except (StopIteration, UnicodeDecodeError):
                break
        return json.dumps({"ok": True, "matches": matches, "truncated": len(matches) >= 50}, ensure_ascii=False)

    if tid == "ast_analyzer":
        path = _resolve(cwd, args["filepath"])
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        out = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append({"kind": type(node).__name__.lower().replace("def", ""), "name": node.name, "line": node.lineno})
        return json.dumps({"ok": True, "symbols": out[:80]}, ensure_ascii=False)

    if tid == "git_integration":
        action = args.get("action", "status")
        cmd = {"status": ["git", "status", "-sb"], "diff": ["git", "diff"], "log": ["git", "log", "--oneline", "-20"]}.get(action)
        if not cmd:
            return json.dumps({"ok": False, "error": "acao invalida"}, ensure_ascii=False)
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        return json.dumps({"ok": p.returncode == 0, "stdout": p.stdout[-4000:], "stderr": p.stderr[-800:]}, ensure_ascii=False)

    if tid == "execute_command":
        cmd = args["command"]
        timeout = int(args.get("timeout_seconds", 60) or 60)
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return json.dumps({"ok": p.returncode == 0, "stdout": p.stdout[-4000:], "stderr": p.stderr[-800:], "returncode": p.returncode}, ensure_ascii=False)

    if tid == "web_search":
        try:
            return web_search(args["query"])
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    if tid == "web_browse":
        try:
            from .browser import web_browse
            return web_browse(args.get("url", ""), args.get("acao", "ler"))
        except ImportError:
            return json.dumps({"ok": False, "error": "playwright nao instalado (pip install playwright && playwright install)"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    return json.dumps({"ok": False, "error": f"tool desconhecida: {tid}"}, ensure_ascii=False)


# esquemas OpenAI (function calling)
SCHEMAS = {
    "read_file": {"type": "object", "properties": {"filepath": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, "required": ["filepath"]},
    "write_file": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]},
    "edit_file": {"type": "object", "properties": {"filepath": {"type": "string"}, "target_block": {"type": "string"}, "replacement_block": {"type": "string"}}, "required": ["filepath", "target_block", "replacement_block"]},
    "list_files": {"type": "object", "properties": {"directory": {"type": "string"}, "depth": {"type": "integer"}}},
    "execute_command": {"type": "object", "properties": {"command": {"type": "string"}, "timeout_seconds": {"type": "integer"}}, "required": ["command"]},
    "search_code": {"type": "object", "properties": {"query": {"type": "string"}, "file_types": {"type": "array", "items": {"type": "string"}}, "case_sensitive": {"type": "boolean"}}, "required": ["query"]},
    "ast_analyzer": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]},
    "git_integration": {"type": "object", "properties": {"action": {"type": "string"}}},
    "web_search": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    "view_image": {"type": "object", "properties": {"image_path": {"type": "string"}, "question": {"type": "string"}}, "required": ["image_path"]},
    "ask_user": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    "web_browse": {"type": "object", "properties": {"url": {"type": "string"}, "acao": {"type": "string"}}, "required": ["url"]},
}


def build_mcp_schemas(manager: MCPClientManager) -> Dict[str, Dict]:
    """Build OpenAI schemas for MCP tools."""
    schemas = {}
    for tool in manager.get_all_tools():
        tid = f"mcp_{tool.server_id}_{tool.name}"
        schemas[tid] = {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": f"MCP tool name (fixed: {tool.name})"},
                "arguments": tool.input_schema,
            },
            "required": ["arguments"],
        }
    return schemas


def tools_payload(ids: list, config: dict) -> list:
    """Lista de tools no formato OpenAI function calling."""
    from .tools import NATIVE_TOOLS
    
    out = []
    manager = get_mcp_manager(config)
    
    # Native tools
    for t in NATIVE_TOOLS:
        if t["id"] not in ids:
            continue
        schema = SCHEMAS.get(t["id"], {"type": "object", "properties": {}})
        out.append({
            "type": "function",
            "function": {"name": t["id"], "description": t["description"], "parameters": schema},
        })
    
    # MCP tools
    mcp_schemas = build_mcp_schemas(manager)
    for t in manager.get_all_tools():
        tid = f"mcp_{t.server_id}_{t.name}"
        if tid not in ids:
            continue
        schema = mcp_schemas.get(tid, {"type": "object", "properties": {}})
        out.append({
            "type": "function",
            "function": {
                "name": tid,
                "description": f"[MCP:{t.server_id}] {t.description}",
                "parameters": schema,
            },
        })
    
    return out
