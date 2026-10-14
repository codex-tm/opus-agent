#!/usr/bin/env python3
"""
OPUS Agent - MCP PostgreSQL Server
Implementa servidor MCP para operações PostgreSQL.
"""

import json
import sys
import os
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None


class MCPPostgreSQLServer:
    """Servidor MCP para operações PostgreSQL."""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or os.environ.get("POSTGRES_CONNECTION_STRING", "")
        self.tools = {
            "execute_query": self._execute_query,
            "execute_many": self._execute_many,
            "list_tables": self._list_tables,
            "describe_table": self._describe_table,
            "list_databases": self._list_databases,
            "list_schemas": self._list_schemas,
            "get_indexes": self._get_indexes,
            "get_foreign_keys": self._get_foreign_keys,
            "explain_query": self._explain_query,
        }

    def _get_connection(self):
        if not psycopg2:
            raise RuntimeError("psycopg2 not installed. Install with: pip install psycopg2-binary")
        if not self.connection_string:
            raise RuntimeError("PostgreSQL connection string required (POSTGRES_CONNECTION_STRING env or --connection-string)")
        return psycopg2.connect(self.connection_string)

    def _execute_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        params = args.get("params", [])
        fetch = args.get("fetch", "all")  # all, one, many, none
        limit = args.get("limit", 1000)
        
        if not query:
            return {"ok": False, "error": "query required"}
        
        try:
            conn = self._get_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                
                if fetch == "none":
                    conn.commit()
                    return {"ok": True, "rowcount": cur.rowcount}
                elif fetch == "one":
                    row = cur.fetchone()
                    return {"ok": True, "row": dict(row) if row else None}
                elif fetch == "many":
                    rows = cur.fetchmany(limit)
                    return {"ok": True, "rows": [dict(r) for r in rows], "rowcount": len(rows)}
                else:  # all
                    rows = cur.fetchall()
                    return {"ok": True, "rows": [dict(r) for r in rows], "rowcount": len(rows)}
        except Exception as e:
            return {"ok": False, "error": f"Query failed: {e}"}
        finally:
            try:
                conn.close()
            except:
                pass

    def _execute_many(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        params_list = args.get("params_list", [])
        
        if not query or not params_list:
            return {"ok": False, "error": "query and params_list required"}
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.executemany(query, params_list)
                conn.commit()
                return {"ok": True, "rowcount": cur.rowcount}
        except Exception as e:
            return {"ok": False, "error": f"Execute many failed: {e}"}
        finally:
            try:
                conn.close()
            except:
                pass

    def _list_tables(self, args: Dict[str, Any]) -> Dict[str, Any]:
        schema = args.get("schema", "public")
        query = """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
        """
        return self._execute_query({"query": query, "params": [schema], "fetch": "all"})

    def _describe_table(self, args: Dict[str, Any]) -> Dict[str, Any]:
        table = args.get("table", "")
        schema = args.get("schema", "public")
        if not table:
            return {"ok": False, "error": "table required"}
        
        query = """
            SELECT column_name, data_type, is_nullable, column_default, 
                   character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        return self._execute_query({"query": query, "params": [schema, table], "fetch": "all"})

    def _list_databases(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
        return self._execute_query({"query": query, "fetch": "all"})

    def _list_schemas(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name"
        return self._execute_query({"query": query, "fetch": "all"})

    def _get_indexes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        table = args.get("table", "")
        schema = args.get("schema", "public")
        if not table:
            return {"ok": False, "error": "table required"}
        
        query = """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
        """
        return self._execute_query({"query": query, "params": [schema, table], "fetch": "all"})

    def _get_foreign_keys(self, args: Dict[str, Any]) -> Dict[str, Any]:
        table = args.get("table", "")
        schema = args.get("schema", "public")
        if not table:
            return {"ok": False, "error": "table required"}
        
        query = """
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
        """
        return self._execute_query({"query": query, "params": [schema, table], "fetch": "all"})

    def _explain_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        analyze = args.get("analyze", False)
        if not query:
            return {"ok": False, "error": "query required"}
        
        explain_query = f"EXPLAIN {'ANALYZE' if analyze else ''} {query}"
        return self._execute_query({"query": explain_query, "fetch": "all"})

    TOOL_SCHEMAS = {
        "execute_query": {"type": "object", "properties": {"query": {"type": "string"}, "params": {"type": "array"}, "fetch": {"type": "string", "enum": ["all", "one", "many", "none"]}, "limit": {"type": "integer"}}, "required": ["query"]},
        "execute_many": {"type": "object", "properties": {"query": {"type": "string"}, "params_list": {"type": "array"}}, "required": ["query", "params_list"]},
        "list_tables": {"type": "object", "properties": {"schema": {"type": "string"}}, "required": []},
        "describe_table": {"type": "object", "properties": {"table": {"type": "string"}, "schema": {"type": "string"}}, "required": ["table"]},
        "list_databases": {"type": "object", "properties": {}, "required": []},
        "list_schemas": {"type": "object", "properties": {}, "required": []},
        "get_indexes": {"type": "object", "properties": {"table": {"type": "string"}, "schema": {"type": "string"}}, "required": ["table"]},
        "get_foreign_keys": {"type": "object", "properties": {"table": {"type": "string"}, "schema": {"type": "string"}}, "required": ["table"]},
        "explain_query": {"type": "object", "properties": {"query": {"type": "string"}, "analyze": {"type": "boolean"}}, "required": ["query"]},
    }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "opus-mcp-postgresql", "version": "1.0.0"}}}
        
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
    parser = argparse.ArgumentParser(description="OPUS MCP PostgreSQL Server")
    parser.add_argument("--connection-string", help="PostgreSQL connection string (or POSTGRES_CONNECTION_STRING env)")
    parser.add_argument("--test", action="store_true", help="Teste rápido")
    args = parser.parse_args()

    if not psycopg2:
        print("psycopg2 not installed. Install with: pip install psycopg2-binary", file=sys.stderr)
        sys.exit(1)

    conn_string = args.connection_string or os.environ.get("POSTGRES_CONNECTION_STRING")
    if not conn_string:
        print("POSTGRES_CONNECTION_STRING required", file=sys.stderr)
        sys.exit(1)

    server = MCPPostgreSQLServer(conn_string)

    if args.test:
        print("Testando PostgreSQL MCP...", file=sys.stderr)
        result = server._execute_query({"query": "SELECT version()", "fetch": "one"})
        print(f"version: {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)
        return

    server.run_stdio()


if __name__ == "__main__":
    main()