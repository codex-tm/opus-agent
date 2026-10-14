#!/usr/bin/env python3
"""
OPUS Agent - MCP GitHub Server
Implementa servidor MCP para operações GitHub via API REST.
"""

import json
import sys
import os
import argparse
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.parse
import base64


class MCPGitHubServer:
    """Servidor MCP para operações GitHub."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.api_base = "https://api.github.com"
        self.tools = {
            "list_repos": self._list_repos,
            "get_repo": self._get_repo,
            "create_repo": self._create_repo,
            "list_issues": self._list_issues,
            "create_issue": self._create_issue,
            "get_issue": self._get_issue,
            "update_issue": self._update_issue,
            "list_prs": self._list_prs,
            "create_pr": self._create_pr,
            "get_pr": self._get_pr,
            "merge_pr": self._merge_pr,
            "list_commits": self._list_commits,
            "get_file": self._get_file,
            "create_file": self._create_file,
            "update_file": self._update_file,
            "delete_file": self._delete_file,
        }

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "opus-mcp-github/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.api_base}{endpoint}"
        headers = self._headers()
        
        if data:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            body = None
        
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            return {"ok": False, "error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            return {"ok": False, "error": f"Request failed: {e}"}

    # Repository operations
    def _list_repos(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner") or args.get("username", "")
        endpoint = f"/users/{owner}/repos" if owner else "/user/repos"
        params = {"per_page": args.get("per_page", 30), "page": args.get("page", 1)}
        if params:
            endpoint += "?" + urllib.parse.urlencode(params)
        return self._request("GET", endpoint)

    def _get_repo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        if not owner or not repo:
            return {"ok": False, "error": "owner and repo required"}
        return self._request("GET", f"/repos/{owner}/{repo}")

    def _create_repo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        data = {
            "name": args.get("name", ""),
            "description": args.get("description", ""),
            "private": args.get("private", False),
            "auto_init": args.get("auto_init", True),
        }
        if not data["name"]:
            return {"ok": False, "error": "name required"}
        return self._request("POST", "/user/repos", data)

    # Issue operations
    def _list_issues(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        if not owner or not repo:
            return {"ok": False, "error": "owner and repo required"}
        params = {
            "state": args.get("state", "open"),
            "per_page": args.get("per_page", 30),
            "page": args.get("page", 1),
        }
        endpoint = f"/repos/{owner}/{repo}/issues?" + urllib.parse.urlencode(params)
        return self._request("GET", endpoint)

    def _get_issue(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        number = args.get("number", 0)
        if not owner or not repo or not number:
            return {"ok": False, "error": "owner, repo, number required"}
        return self._request("GET", f"/repos/{owner}/{repo}/issues/{number}")

    def _create_issue(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        title = args.get("title", "")
        body = args.get("body", "")
        if not owner or not repo or not title:
            return {"ok": False, "error": "owner, repo, title required"}
        data = {"title": title, "body": body}
        if "labels" in args:
            data["labels"] = args["labels"]
        if "assignees" in args:
            data["assignees"] = args["assignees"]
        return self._request("POST", f"/repos/{owner}/{repo}/issues", data)

    def _update_issue(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        number = args.get("number", 0)
        if not owner or not repo or not number:
            return {"ok": False, "error": "owner, repo, number required"}
        data = {}
        for field in ["title", "body", "state", "labels", "assignees"]:
            if field in args:
                data[field] = args[field]
        return self._request("PATCH", f"/repos/{owner}/{repo}/issues/{number}", data)

    # PR operations
    def _list_prs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        if not owner or not repo:
            return {"ok": False, "error": "owner and repo required"}
        params = {
            "state": args.get("state", "open"),
            "per_page": args.get("per_page", 30),
            "page": args.get("page", 1),
        }
        endpoint = f"/repos/{owner}/{repo}/pulls?" + urllib.parse.urlencode(params)
        return self._request("GET", endpoint)

    def _get_pr(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        number = args.get("number", 0)
        if not owner or not repo or not number:
            return {"ok": False, "error": "owner, repo, number required"}
        return self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")

    def _create_pr(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        title = args.get("title", "")
        head = args.get("head", "")
        base = args.get("base", "main")
        body = args.get("body", "")
        if not owner or not repo or not title or not head:
            return {"ok": False, "error": "owner, repo, title, head required"}
        data = {"title": title, "head": head, "base": base, "body": body}
        return self._request("POST", f"/repos/{owner}/{repo}/pulls", data)

    def _merge_pr(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        number = args.get("number", 0)
        if not owner or not repo or not number:
            return {"ok": False, "error": "owner, repo, number required"}
        data = {
            "commit_title": args.get("commit_title", ""),
            "commit_message": args.get("commit_message", ""),
            "merge_method": args.get("merge_method", "merge"),
        }
        return self._request("PUT", f"/repos/{owner}/{repo}/pulls/{number}/merge", data)

    # Commit operations
    def _list_commits(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        if not owner or not repo:
            return {"ok": False, "error": "owner and repo required"}
        params = {
            "sha": args.get("sha", ""),
            "path": args.get("path", ""),
            "per_page": args.get("per_page", 30),
            "page": args.get("page", 1),
        }
        params = {k: v for k, v in params.items() if v}
        endpoint = f"/repos/{owner}/{repo}/commits?" + urllib.parse.urlencode(params)
        return self._request("GET", endpoint)

    # File operations
    def _get_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        path = args.get("path", "")
        ref = args.get("ref", "")
        if not owner or not repo or not path:
            return {"ok": False, "error": "owner, repo, path required"}
        params = {"ref": ref} if ref else {}
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        if params:
            endpoint += "?" + urllib.parse.urlencode(params)
        return self._request("GET", endpoint)

    def _create_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        path = args.get("path", "")
        content = args.get("content", "")
        message = args.get("message", "Create file via Opus")
        branch = args.get("branch", "main")
        if not owner or not repo or not path or not content:
            return {"ok": False, "error": "owner, repo, path, content required"}
        data = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        return self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", data)

    def _update_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        path = args.get("path", "")
        content = args.get("content", "")
        sha = args.get("sha", "")
        message = args.get("message", "Update file via Opus")
        branch = args.get("branch", "main")
        if not owner or not repo or not path or not content or not sha:
            return {"ok": False, "error": "owner, repo, path, content, sha required"}
        data = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "sha": sha,
            "branch": branch,
        }
        return self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", data)

    def _delete_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        owner = args.get("owner", "")
        repo = args.get("repo", "")
        path = args.get("path", "")
        sha = args.get("sha", "")
        message = args.get("message", "Delete file via Opus")
        branch = args.get("branch", "main")
        if not owner or not repo or not path or not sha:
            return {"ok": False, "error": "owner, repo, path, sha required"}
        data = {"message": message, "sha": sha, "branch": branch}
        return self._request("DELETE", f"/repos/{owner}/{repo}/contents/{path}", data)

    # Schemas
    TOOL_SCHEMAS = {
        "list_repos": {"type": "object", "properties": {"owner": {"type": "string"}, "per_page": {"type": "integer"}, "page": {"type": "integer"}}, "required": []},
        "get_repo": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}}, "required": ["owner", "repo"]},
        "create_repo": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "private": {"type": "boolean"}, "auto_init": {"type": "boolean"}}, "required": ["name"]},
        "list_issues": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "state": {"type": "string"}, "per_page": {"type": "integer"}, "page": {"type": "integer"}}, "required": ["owner", "repo"]},
        "get_issue": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "number": {"type": "integer"}}, "required": ["owner", "repo", "number"]},
        "create_issue": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}, "labels": {"type": "array", "items": {"type": "string"}}, "assignees": {"type": "array", "items": {"type": "string"}}}, "required": ["owner", "repo", "title"]},
        "update_issue": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "number": {"type": "integer"}, "title": {"type": "string"}, "body": {"type": "string"}, "state": {"type": "string"}, "labels": {"type": "array", "items": {"type": "string"}}, "assignees": {"type": "array", "items": {"type": "string"}}}, "required": ["owner", "repo", "number"]},
        "list_prs": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "state": {"type": "string"}, "per_page": {"type": "integer"}, "page": {"type": "integer"}}, "required": ["owner", "repo"]},
        "get_pr": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "number": {"type": "integer"}}, "required": ["owner", "repo", "number"]},
        "create_pr": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "title": {"type": "string"}, "head": {"type": "string"}, "base": {"type": "string"}, "body": {"type": "string"}}, "required": ["owner", "repo", "title", "head"]},
        "merge_pr": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "number": {"type": "integer"}, "commit_title": {"type": "string"}, "commit_message": {"type": "string"}, "merge_method": {"type": "string"}}, "required": ["owner", "repo", "number"]},
        "list_commits": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "sha": {"type": "string"}, "path": {"type": "string"}, "per_page": {"type": "integer"}, "page": {"type": "integer"}}, "required": ["owner", "repo"]},
        "get_file": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}, "ref": {"type": "string"}}, "required": ["owner", "repo", "path"]},
        "create_file": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}, "content": {"type": "string"}, "message": {"type": "string"}, "branch": {"type": "string"}}, "required": ["owner", "repo", "path", "content"]},
        "update_file": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}, "content": {"type": "string"}, "sha": {"type": "string"}, "message": {"type": "string"}, "branch": {"type": "string"}}, "required": ["owner", "repo", "path", "content", "sha"]},
        "delete_file": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "path": {"type": "string"}, "sha": {"type": "string"}, "message": {"type": "string"}, "branch": {"type": "string"}}, "required": ["owner", "repo", "path", "sha"]},
    }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "opus-mcp-github", "version": "1.0.0"}}}
        
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
    parser = argparse.ArgumentParser(description="OPUS MCP GitHub Server")
    parser.add_argument("--token", help="GitHub token (or GITHUB_TOKEN env)")
    parser.add_argument("--test", action="store_true", help="Teste rápido")
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN required", file=sys.stderr)
        sys.exit(1)

    server = MCPGitHubServer(token)

    if args.test:
        print("Testando GitHub MCP...", file=sys.stderr)
        result = server._list_repos({"owner": "octocat", "per_page": 5})
        print(f"list_repos: {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)
        return

    server.run_stdio()


if __name__ == "__main__":
    main()