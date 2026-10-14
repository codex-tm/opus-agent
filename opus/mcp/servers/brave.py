#!/usr/bin/env python3
"""
OPUS Agent - MCP Brave Search Server
Implementa servidor MCP para busca web via Brave Search API.
"""

import json
import sys
import os
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.parse


class MCPBraveSearchServer:
    """Servidor MCP para busca web via Brave Search API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        self.api_base = "https://api.search.brave.com/res/v1"
        self.tools = {
            "web_search": self._web_search,
            "news_search": self._news_search,
        }

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_base}{endpoint}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self._headers())
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            return {"ok": False, "error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            return {"ok": False, "error": f"Request failed: {e}"}

    def _web_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        count = args.get("count", 10)
        offset = args.get("offset", 0)
        search_lang = args.get("search_lang", "")
        country = args.get("country", "")
        safesearch = args.get("safesearch", "moderate")
        freshness = args.get("freshness", "")
        
        if not query:
            return {"ok": False, "error": "query required"}
        
        params = {
            "q": query,
            "count": min(count, 20),
            "offset": offset,
            "safesearch": safesearch,
        }
        if search_lang:
            params["search_lang"] = search_lang
        if country:
            params["country"] = country
        if freshness:
            params["freshness"] = freshness
        
        result = self._request("/web/search", params)
        
        if "ok" in result and not result.get("ok", True):
            return result
        
        # Normalize response
        web_results = result.get("web", {}).get("results", [])
        normalized = {
            "ok": True,
            "query": query,
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                    "age": r.get("age", ""),
                    "language": r.get("language", ""),
                    "page_favicon": r.get("page_favicon", ""),
                }
                for r in web_results
            ],
            "total_results": result.get("web", {}).get("total_results", 0),
        }
        return normalized

    def _news_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        count = args.get("count", 10)
        offset = args.get("offset", 0)
        freshness = args.get("freshness", "")
        safesearch = args.get("safesearch", "moderate")
        
        if not query:
            return {"ok": False, "error": "query required"}
        
        params = {
            "q": query,
            "count": min(count, 20),
            "offset": offset,
            "safesearch": safesearch,
        }
        if freshness:
            params["freshness"] = freshness
        
        result = self._request("/news/search", params)
        
        if "ok" in result and not result.get("ok", True):
            return result
        
        news_results = result.get("news", {}).get("results", [])
        normalized = {
            "ok": True,
            "query": query,
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                    "age": r.get("age", ""),
                    "source": r.get("source", ""),
                    "image": r.get("image", ""),
                }
                for r in news_results
            ],
            "total_results": result.get("news", {}).get("total_results", 0),
        }
        return normalized

    TOOL_SCHEMAS = {
        "web_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "count": {"type": "integer", "minimum": 1, "maximum": 20},
                "offset": {"type": "integer", "minimum": 0},
                "search_lang": {"type": "string"},
                "country": {"type": "string"},
                "safesearch": {"type": "string", "enum": ["strict", "moderate", "off"]},
                "freshness": {"type": "string"},
            },
            "required": ["query"],
        },
        "news_search": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "count": {"type": "integer", "minimum": 1, "maximum": 20},
                "offset": {"type": "integer", "minimum": 0},
                "freshness": {"type": "string"},
                "safesearch": {"type": "string", "enum": ["strict", "moderate", "off"]},
            },
            "required": ["query"],
        },
    }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "opus-mcp-brave", "version": "1.0.0"}}}
        
        elif method == "tools/list":
            tool_list = []
            for name, fn in self.tools.items():
                tool_list.append({"name": name, "description": fn.__doc__ or f"MCP tool: {name}", "inputSchema": self.TOOL_SCHEMAS.get(name, {"type": "object", "properties": {}})})
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tool_list}}

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if tool_name not in self.tools:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool nao encontrada: {tool_name}"}}
            try:
                result = self.tools[tool_name](tool_args)
                return {"jsonrpc": "2.0", "id": request_id, "result": result}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": f"Erro interno: {e}"}}

        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Metodo nao suportado: {method}"}}

    def run_stdio(self):
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
    parser = argparse.ArgumentParser(description="OPUS MCP Brave Search Server")
    parser.add_argument("--api-key", help="Brave API key (or BRAVE_API_KEY env)")
    parser.add_argument("--test", action="store_true", help="Teste rápido")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("BRAVE_API_KEY")
    if not api_key:
        print("BRAVE_API_KEY required", file=sys.stderr)
        sys.exit(1)

    server = MCPBraveSearchServer(api_key)

    if args.test:
        print("Testando Brave Search MCP...", file=sys.stderr)
        result = server._web_search({"query": "opus agent", "count": 5})
        print(f"web_search: {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)
        return

    server.run_stdio()


if __name__ == "__main__":
    main()