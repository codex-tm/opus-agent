#!/usr/bin/env python3
"""
OPUS Agent - MCP Filesystem Server
Implementa servidor MCP para acesso ao sistema de arquivos local.
Seguro: restrito ao diretório de trabalho (cwd) do projeto.
"""

import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse


class MCPFileSystemServer:
    """Servidor MCP para operações de arquivo restritas ao workspace."""

    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace or os.getcwd()).resolve()
        self.tools = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "list_files": self._list_files,
            "glob_files": self._glob_files,
            "file_info": self._file_info,
        }

    def _resolve(self, path: str) -> Path:
        """Resolve caminho relativo ao workspace, impedindo path traversal."""
        p = (self.workspace / path).resolve()
        try:
            p.relative_to(self.workspace)
        except ValueError:
            raise PermissionError(f"Caminho fora do workspace: {path}")
        return p

    def _read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        filepath = args.get("filepath", "")
        start = args.get("start_line", 1)
        end = args.get("end_line", None)
        try:
            p = self._resolve(filepath)
            if not p.exists():
                return {"ok": False, "error": f"Arquivo nao encontrado: {filepath}"}
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            if end is None or end > len(lines):
                end = len(lines)
            selected = lines[start - 1 : end]
            return {
                "ok": True,
                "content": "\n".join(selected),
                "total_lines": len(lines),
                "start_line": start,
                "end_line": end,
            }
        except PermissionError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Erro ao ler: {e}"}

    def _write_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        filepath = args.get("filepath", "")
        content = args.get("content", "")
        try:
            p = self._resolve(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"ok": True, "message": f"Arquivo escrito: {filepath}"}
        except PermissionError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Erro ao escrever: {e}"}

    def _edit_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        filepath = args.get("filepath", "")
        target = args.get("target_block", "")
        replacement = args.get("replacement_block", "")
        try:
            p = self._resolve(filepath)
            if not p.exists():
                return {"ok": False, "error": f"Arquivo nao encontrado: {filepath}"}
            old_content = p.read_text(encoding="utf-8", errors="replace")
            if target not in old_content:
                return {"ok": False, "error": "Bloco alvo nao encontrado no arquivo"}
            new_content = old_content.replace(target, replacement, 1)
            p.write_text(new_content, encoding="utf-8")
            return {
                "ok": True,
                "old": target,
                "new": replacement,
                "message": f"Arquivo editado: {filepath}",
            }
        except PermissionError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Erro ao editar: {e}"}

    def _list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        directory = args.get("directory", ".")
        depth = args.get("depth", 3)
        pattern = args.get("pattern", None)
        try:
            base = self._resolve(directory)
            if not base.exists() or not base.is_dir():
                return {"ok": False, "error": f"Diretorio nao encontrado: {directory}"}

            def walk(d: Path, current_depth: int = 0):
                if current_depth > depth:
                    return []
                items = []
                for entry in sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    if entry.name.startswith("."):
                        continue
                    rel = entry.relative_to(self.workspace)
                    if pattern and not entry.match(pattern):
                        continue
                    item = {
                        "name": entry.name,
                        "path": str(rel),
                        "type": "dir" if entry.is_dir() else "file",
                        "size": entry.stat().st_size if entry.is_file() else 0,
                    }
                    if entry.is_dir():
                        item["children"] = walk(entry, current_depth + 1)
                    items.append(item)
                return items

            return {"ok": True, "tree": walk(base)}
        except PermissionError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Erro ao listar: {e}"}

    def _glob_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pattern = args.get("pattern", "**/*")
        try:
            base = self.workspace
            files = []
            for p in base.rglob(pattern):
                try:
                    if p.is_file():
                        rel = p.relative_to(base)
                        files.append({
                            "path": str(rel),
                            "size": p.stat().st_size,
                        })
                except ValueError:
                    continue
            return {"ok": True, "files": files}
        except Exception as e:
            return {"ok": False, "error": f"Erro no glob: {e}"}

    def _file_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        filepath = args.get("filepath", "")
        try:
            p = self._resolve(filepath)
            if not p.exists():
                return {"ok": False, "error": f"Arquivo nao encontrado: {filepath}"}
            stat = p.stat()
            return {
                "ok": True,
                "path": str(p.relative_to(self.workspace)),
                "size": stat.st_size,
                "is_dir": p.is_dir(),
                "is_file": p.is_file(),
                "modified": stat.st_mtime,
            }
        except PermissionError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Erro ao obter info: {e}"}

    # Schemas explícitos para cada tool (inspect.signature vê apenas args dict)
    TOOL_SCHEMAS = {
        "read_file": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Caminho do arquivo relativo ao workspace"},
                "start_line": {"type": "integer", "description": "Linha inicial (1-indexed)"},
                "end_line": {"type": "integer", "description": "Linha final (inclusive)"},
            },
            "required": ["filepath"],
        },
        "write_file": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Caminho do arquivo relativo ao workspace"},
                "content": {"type": "string", "description": "Conteúdo a escrever"},
            },
            "required": ["filepath", "content"],
        },
        "edit_file": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Caminho do arquivo relativo ao workspace"},
                "target_block": {"type": "string", "description": "Bloco exato a substituir"},
                "replacement_block": {"type": "string", "description": "Novo bloco"},
            },
            "required": ["filepath", "target_block", "replacement_block"],
        },
        "list_files": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Diretório base (default: .)"},
                "depth": {"type": "integer", "description": "Profundidade máxima (default: 3)"},
                "pattern": {"type": "string", "description": "Glob pattern opcional"},
            },
            "required": [],
        },
        "glob_files": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (default: **/*)"},
            },
            "required": [],
        },
        "file_info": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Caminho do arquivo relativo ao workspace"},
            },
            "required": ["filepath"],
        },
    }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Processa uma requisição MCP."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "opus-mcp-fs", "version": "1.0.0"},
                },
            }

        elif method == "tools/list":
            tool_list = []
            for name, fn in self.tools.items():
                tool_list.append({
                    "name": name,
                    "description": fn.__doc__ or f"MCP tool: {name}",
                    "inputSchema": self.TOOL_SCHEMAS.get(name, {"type": "object", "properties": {}}),
                })
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tool_list},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if tool_name not in self.tools:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Tool nao encontrada: {tool_name}"},
                }
            try:
                result = self.tools[tool_name](tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result,
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Erro interno: {e}"},
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Metodo nao suportado: {method}"},
            }

    def run_stdio(self):
        """Loop principal stdio (JSON-RPC)."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = self.handle_request(request)
            print(json.dumps(response, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description="OPUS MCP Filesystem Server")
    parser.add_argument("--workspace", help="Diretório workspace (default: cwd)")
    parser.add_argument("--test", action="store_true", help="Teste rápido das ferramentas")
    args = parser.parse_args()

    server = MCPFileSystemServer(args.workspace)

    if args.test:
        # Teste rápido
        print("Testando ferramentas MCP...", file=sys.stderr)
        tests = [
            ("list_files", {"directory": "."}),
            ("write_file", {"filepath": "test_mcp.txt", "content": "Hello MCP"}),
            ("read_file", {"filepath": "test_mcp.txt"}),
            ("edit_file", {"filepath": "test_mcp.txt", "target_block": "Hello MCP", "replacement_block": "Hello MCP edited"}),
            ("read_file", {"filepath": "test_mcp.txt"}),
            ("file_info", {"filepath": "test_mcp.txt"}),
            ("glob_files", {"pattern": "**/*.txt"}),
        ]
        for tool, params in tests:
            result = server.tools[tool](params)
            print(f"{tool}: {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)
        # Cleanup
        try:
            (server.workspace / "test_mcp.txt").unlink()
        except Exception:
            pass
        print("Testes concluidos.", file=sys.stderr)
        return

    server.run_stdio()


if __name__ == "__main__":
    main()