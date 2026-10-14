import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_DIR = Path.home() / ".opus"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0.0",
    "theme": "cyberpunk_neon",
    "default_provider": "anthropic",
    "default_model": "claude-3-5-sonnet-20241022",
    "auto_approve_tools": False,
    "system_instructions": "Você é o OPUS Agent, um engenheiro de software autônomo de nível sênior.",
    "api_keys": {
        "anthropic": "",
        "openai": "",
        "google": "",
        "openrouter": "",
        "deepseek": "",
        "groq": ""
    },
    "endpoints": {
        "ollama": {
            "name": "Ollama Local",
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.1:latest",
            "enabled": True
        },
        "anthropic": {
            "name": "Anthropic Claude Official",
            "base_url": "https://api.anthropic.com/v1",
            "default_model": "claude-3-5-sonnet-20241022",
            "enabled": True
        },
        "openai": {
            "name": "OpenAI Official",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "enabled": True
        },
        "google": {
            "name": "Google Gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "default_model": "gemini-2.0-flash",
            "enabled": True
        },
        "deepseek": {
            "name": "DeepSeek API",
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-coder",
            "enabled": True
        },
        "groq": {
            "name": "Groq Ultra Fast",
            "base_url": "https://api.groq.com/openai/v1",
            "default_model": "llama-3.3-70b-versatile",
            "enabled": True
        }
    },
    "mcp_servers": {
        "filesystem": {
            "name": "Local Filesystem Server",
            "command": "python -m opus.mcp.fs",
            "enabled": True,
            "description": "Acesso seguro e restrito ao diretório do projeto."
        }
    },
    "reasoning": "medium",
    "tools_config": {
        "file_operations": True,
        "terminal_execution": True,
        "search_code": True,
        "web_fetch": True,
        "git_integration": True,
        "ast_analysis": True,
        "web_search": True
    }
}

def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR

def load_config() -> Dict[str, Any]:
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
            # Mescla recursivamente com defaults para não perder novas chaves
            merged = DEFAULT_CONFIG.copy()
            merged.update(saved)
            # Preservar chaves aninhadas
            for key in ["api_keys", "endpoints", "mcp_servers", "tools_config"]:
                if key in saved:
                    merged[key] = {**DEFAULT_CONFIG.get(key, {}), **saved[key]}
            return merged
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]) -> bool:
    try:
        ensure_config_dir()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")
        return False

def get_api_key(provider: str, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    cfg = config or load_config()
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY"
    }
    env_var = env_vars.get(provider.lower())
    if env_var and os.environ.get(env_var):
        return os.environ.get(env_var)
    return cfg.get("api_keys", {}).get(provider.lower(), "")
