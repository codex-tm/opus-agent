"""
OPUS Agent - Core Tools Registry & Native Capabilities
Catálogo completo de ferramentas nativas e integração com MCP.
"""

from typing import Dict, List, Any

TOOL_CATEGORIES = {
    "files": "Operações no Sistema de Arquivos",
    "terminal": "Execução de Comandos & Shell",
    "search": "Busca Semântica & Análise de Código",
    "git": "Controle de Versão & Repositório",
    "mcp": "Extensões Model Context Protocol (MCP)",
    "vision": "Visao / imagem",
    "browser": "Navegador (Playwright)",
    "web": "Busca web",
    "ask": "Clarificacao"
}

NATIVE_TOOLS: List[Dict[str, Any]] = [
    {
        "id": "read_file",
        "name": "Leitor de Arquivos",
        "category": "files",
        "icon": "[TXT]",
        "description": "Lê conteúdo de arquivos com destaque de sintaxe e paginação inteligente.",
        "dangerous": False,
        "parameters": ["filepath", "start_line", "end_line"],
        "status": "ready"
    },
    {
        "id": "write_file",
        "name": "Criador de Arquivos",
        "category": "files",
        "icon": "[NEW]",
        "description": "Cria novos arquivos ou substitui conteúdo com integridade atômica.",
        "dangerous": True,
        "parameters": ["filepath", "content"],
        "status": "ready"
    },
    {
        "id": "edit_file",
        "name": "Editor Cirúrgico de Código",
        "category": "files",
        "icon": "[EDIT]",
        "description": "Substitui blocos contíguos de código gerando Diff visual colorido antes de aplicar.",
        "dangerous": True,
        "parameters": ["filepath", "target_block", "replacement_block"],
        "status": "ready"
    },
    {
        "id": "list_files",
        "name": "Explorador de Diretórios",
        "category": "files",
        "icon": "[DIR]",
        "description": "Mapeia a árvore de arquivos respeitando regras do .gitignore.",
        "dangerous": False,
        "parameters": ["directory", "depth", "pattern"],
        "status": "ready"
    },
    {
        "id": "execute_command",
        "name": "Terminal Executor",
        "category": "terminal",
        "icon": "[EXEC]",
        "description": "Executa comandos no PowerShell / CMD com captura de stdout, stderr e timeouts.",
        "dangerous": True,
        "parameters": ["command", "cwd", "timeout_seconds"],
        "status": "ready"
    },
    {
        "id": "search_code",
        "name": "Buscador de Código (Fast Grep)",
        "category": "search",
        "icon": "[FIND]",
        "description": "Pesquisa termos ou padrões Regex através de todo o repositório em alta velocidade.",
        "dangerous": False,
        "parameters": ["query", "file_types", "case_sensitive"],
        "status": "ready"
    },
    {
        "id": "ast_analyzer",
        "name": "Analisador AST de Código",
        "category": "search",
        "icon": "[AST]",
        "description": "Analisa a árvore de sintaxe abstrata para listar funções, classes e imports.",
        "dangerous": False,
        "parameters": ["filepath"],
        "status": "ready"
    },
    {
        "id": "view_image",
        "name": "Analisar Imagem (visao)",
        "category": "vision",
        "icon": "[IMG]",
        "description": "Descreve uma imagem do clipboard (Ctrl+V) ou de um caminho.",
        "dangerous": False,
        "parameters": ["image_path"],
        "status": "ready"
    },
    {
        "id": "web_browse",
        "name": "Navegador",
        "category": "browser",
        "icon": "[WEB]",
        "description": "Busca e le paginas da web via Playwright.",
        "dangerous": False,
        "parameters": ["url", "acao"],
        "status": "ready"
    },
    {
        "id": "web_search",
        "name": "Busca Web",
        "category": "web",
        "icon": "[FIND]",
        "description": "Pesquisa na web pelo termo (DuckDuckGo, sem chave).",
        "dangerous": False,
        "parameters": ["query"],
        "status": "ready"
    },
    {
        "id": "ask_user",
        "name": "Perguntar ao Usuario",
        "category": "ask",
        "icon": "[ASK]",
        "description": "Pede esclarecimento quando o agente esta em duvida.",
        "dangerous": False,
        "parameters": ["question"],
        "status": "ready"
    },
    {
        "id": "git_integration",
        "name": "Git Companion",
        "category": "git",
        "icon": "[GIT]",
        "description": "Verifica diffs, status de arquivos modificados, histórico de commits e branchs.",
        "dangerous": False,
        "parameters": ["action"],
        "status": "ready"
    }
]

def get_all_tools(config: dict) -> List[Dict[str, Any]]:
    """Retorna lista de todas as ferramentas nativas e MCPs configuradas."""
    tools = list(NATIVE_TOOLS)
    
    # Adicionar servidores MCP do config
    mcp_servers = config.get("mcp_servers", {})
    for srv_id, srv_data in mcp_servers.items():
        tools.append({
            "id": f"mcp_{srv_id}",
            "name": f"MCP: {srv_data.get('name', srv_id)}",
            "category": "mcp",
            "icon": "[MCP]",
            "description": srv_data.get("description", "Servidor externo via protocolo MCP."),
            "dangerous": True,
            "parameters": ["tool_name", "arguments"],
            "status": "active" if srv_data.get("enabled", True) else "disabled"
        })
        
    return tools
