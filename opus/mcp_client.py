"""
OPUS Agent v2 - MCP Client (JSON-RPC 2.0 over stdio).

Connects to MCP servers, initializes them, lists tools, and calls tools.
Each server runs as a subprocess with stdio transport.
"""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class MCPTool:
    """Tool exposed by an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_id: str


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    server_id: str
    name: str
    command: str
    enabled: bool = True
    description: str = ""
    cwd: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0


class MCPClient:
    """JSON-RPC 2.0 client for MCP servers over stdio."""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.proc: Optional[subprocess.Popen] = None
        self.initialized = False
        self.tools: List[MCPTool] = []
        self._request_id = 0
        self._pending: Dict[int, Any] = {}
    
    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
    
    def start(self) -> bool:
        """Start the MCP server process and initialize."""
        try:
            cwd = Path(self.config.cwd) if self.config.cwd else Path.cwd()
            env = os.environ.copy()
            env.update(self.config.env)
            
            self.proc = subprocess.Popen(
                self.config.command,
                shell=True,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=env,
                bufsize=1,  # Line buffered
            )
            
            # Initialize
            init_result = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "opus-agent", "version": "2.0.0"}
            })
            
            if "error" in init_result:
                self.stop()
                return False
            
            # List tools
            tools_result = self._send_request("tools/list", {})
            if "result" in tools_result and "tools" in tools_result["result"]:
                self.tools = [
                    MCPTool(
                        name=t["name"],
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
                        server_id=self.config.server_id
                    )
                    for t in tools_result["result"]["tools"]
                ]
            
            self.initialized = True
            return True
            
        except Exception as e:
            print(f"MCP client start error: {e}")
            self.stop()
            return False
    
    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC request and wait for response."""
        if not self.proc or self.proc.poll() is not None:
            return {"error": {"code": -32603, "message": "Server not running"}}
        
        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        
        try:
            # Write request
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            
            # Read response (with timeout)
            start = time.time()
            while time.time() - start < self.config.timeout:
                line = self.proc.stdout.readline()
                if not line:
                    time.sleep(0.01)
                    continue
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    response = json.loads(line)
                    if response.get("id") == req_id:
                        if "error" in response:
                            return {"error": response["error"]}
                        return {"result": response.get("result", {})}
                except json.JSONDecodeError:
                    continue
            
            return {"error": {"code": -32603, "message": "Request timeout"}}
            
        except Exception as e:
            return {"error": {"code": -32603, "message": str(e)}}
    
    def list_tools(self) -> List[MCPTool]:
        """Return cached tools list."""
        return self.tools
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self.initialized:
            return {"error": {"code": -32603, "message": "Client not initialized"}}
        
        result = self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        
        if "error" in result:
            return {"ok": False, "error": result["error"].get("message", "Unknown error")}
        
        return {"ok": True, "result": result.get("result", {})}
    
    def stop(self):
        """Stop the MCP server process."""
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            except Exception:
                pass
            self.proc = None
            self.initialized = False
            self.tools = []
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class MCPClientManager:
    """Manages multiple MCP clients."""
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.configs: Dict[str, MCPServerConfig] = {}
    
    def register(self, config: MCPServerConfig):
        self.configs[config.server_id] = config
    
    def start_all(self) -> Dict[str, bool]:
        """Start all registered clients. Returns dict of server_id -> success."""
        results = {}
        for server_id, config in self.configs.items():
            if not config.enabled:
                results[server_id] = False
                continue
            client = MCPClient(config)
            success = client.start()
            if success:
                self.clients[server_id] = client
            results[server_id] = success
        return results
    
    def get_client(self, server_id: str) -> Optional[MCPClient]:
        return self.clients.get(server_id)
    
    def get_all_tools(self) -> List[MCPTool]:
        """Get all tools from all connected clients."""
        all_tools = []
        for client in self.clients.values():
            all_tools.extend(client.tools)
        return all_tools
    
    def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific server."""
        client = self.clients.get(server_id)
        if not client:
            return {"ok": False, "error": f"Server {server_id} not connected"}
        return client.call_tool(tool_name, arguments)
    
    def stop_all(self):
        for client in self.clients.values():
            client.stop()
        self.clients.clear()


def load_mcp_config(config_path: Path) -> Dict[str, MCPServerConfig]:
    """Load MCP server configs from TOML file."""
    import tomllib
    if not config_path.exists():
        return {}
    
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    
    servers = {}
    for server_id, srv_data in data.get("mcp_servers", {}).items():
        servers[server_id] = MCPServerConfig(
            server_id=server_id,
            name=srv_data.get("name", server_id),
            command=srv_data.get("command", ""),
            enabled=srv_data.get("enabled", True),
            description=srv_data.get("description", ""),
            cwd=srv_data.get("cwd"),
            env=srv_data.get("env", {}),
            timeout=srv_data.get("timeout", 30.0),
        )
    return servers


if __name__ == "__main__":
    import os
    # Quick test with filesystem server
    config = MCPServerConfig(
        server_id="filesystem",
        name="Local Filesystem",
        command="python -m opus.mcp.fs",
        cwd=str(Path.cwd()),
    )
    
    with MCPClient(config) as client:
        print(f"Tools: {[t.name for t in client.tools]}")
        result = client.call_tool("list_files", {"directory": ".", "depth": 2})
        print(f"list_files result: {json.dumps(result, indent=2, ensure_ascii=False)}")