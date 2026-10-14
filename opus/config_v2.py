"""
OPUS Agent v2 - Config loader with TOML + OS Keyring support.

Secrets (API keys) are stored in OS keyring:
- Windows: Credential Manager (via keyring backend)
- Linux: secretstorage (DBus Secret Service)
- macOS: Keychain

Config structure is TOML at ~/.opus/config_v2/config.toml
Sessions DB at ~/.opus/config_v2/opus.db
"""

import os
import json
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional
import keyring

CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".opus")) / "opus" / "config_v2"
CONFIG_FILE = CONFIG_DIR / "config.toml"
DB_FILE = CONFIG_DIR / "opus.db"
KEYRING_SERVICE = "opus-agent"

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "2.0.0",
    "theme": "cyberpunk_neon",
    "default_provider": "anthropic",
    "default_model": "claude-3-5-sonnet-20241022",
    "auto_approve_tools": False,
    "system_instructions": "Voce e o OPUS Agent, um engenheiro de software autonomo de nivel senior.",
    "endpoints": {
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
        },
        "ollama": {
            "name": "Ollama Local",
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.1:latest",
            "enabled": True
        },
        "openrouter": {
            "name": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "default_model": "anthropic/claude-3.5-sonnet",
            "enabled": True
        }
    },
    "mcp_servers": {
        "filesystem": {
            "name": "Local Filesystem Server",
            "command": "python -m opus.mcp.fs",
            "enabled": True,
            "description": "Acesso seguro e restrito ao diretorio do projeto."
        }
    },
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

ENV_VAR_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY"
}


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_config() -> Dict[str, Any]:
    """Carrega config do TOML, faz merge com defaults, resolve secrets do keyring/env."""
    ensure_config_dir()
    
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, "rb") as f:
            saved = tomllib.load(f)
        
        # Merge recursivo preservando estrutura
        merged = DEFAULT_CONFIG.copy()
        _deep_merge(merged, saved)
        
        # Resolve API keys: env var > keyring > config file (empty)
        for provider in merged.get("endpoints", {}):
            key = _get_api_key(provider)
            if key:
                # Armazena internamente para uso, mas NÃO salva no TOML
                merged.setdefault("_resolved_keys", {})[provider] = key
        
        return merged
    except Exception as e:
        print(f"Erro ao carregar config: {e}")
        return DEFAULT_CONFIG.copy()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Merge recursivo preservando chaves aninhadas."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def save_config(config: Dict[str, Any]) -> bool:
    """Salva config no TOML (SEM secrets - eles vão pro keyring)."""
    try:
        ensure_config_dir()
        
        # Remove chaves internas antes de salvar
        to_save = {k: v for k, v in config.items() if not k.startswith("_")}
        
        import tomli_w
        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(to_save, f)
        return True
    except Exception as e:
        print(f"Erro ao salvar config: {e}")
        return False


def _get_api_key(provider: str) -> Optional[str]:
    """Resolve API key: env var > keyring > config (vazio)."""
    # 1. Environment variable (highest priority)
    env_var = ENV_VAR_MAP.get(provider.lower())
    if env_var and os.environ.get(env_var):
        return os.environ.get(env_var)
    
    # 2. OS Keyring
    try:
        key = keyring.get_password(KEYRING_SERVICE, provider)
        if key:
            return key
    except Exception:
        pass
    
    return None


def set_api_key(provider: str, key: str) -> bool:
    """Armazena API key no OS keyring."""
    try:
        keyring.set_password(KEYRING_SERVICE, provider, key)
        return True
    except Exception as e:
        print(f"Erro ao salvar key no keyring: {e}")
        return False


def delete_api_key(provider: str) -> bool:
    """Remove API key do keyring."""
    try:
        keyring.delete_password(KEYRING_SERVICE, provider)
        return True
    except Exception:
        return False


def get_api_key(provider: str, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Interface compatível com código antigo."""
    return _get_api_key(provider)


def get_db_path() -> Path:
    """Retorna caminho do banco de dados SQLite unificado."""
    ensure_config_dir()
    return DB_FILE


def migrate_from_v1() -> bool:
    """Migra config v1 (JSON) para v2 (TOML + keyring)."""
    v1_config = Path.home() / ".opus" / "config.json"
    v1_db = Path.home() / ".opus" / "sessions.db"
    
    if not v1_config.exists():
        return False
    
    try:
        # Carrega v1
        with open(v1_config, "r", encoding="utf-8") as f:
            old = json.load(f)
        
        # Extrai API keys e salva no keyring
        for provider, key in old.get("api_keys", {}).items():
            if key and provider in ENV_VAR_MAP:
                set_api_key(provider, key)
        
        # Prepara config v2
        new_config = DEFAULT_CONFIG.copy()
        _deep_merge(new_config, {
            "theme": old.get("theme", "cyberpunk_neon"),
            "default_provider": old.get("default_provider", "anthropic"),
            "default_model": old.get("default_model", "claude-3-5-sonnet-20241022"),
            "auto_approve_tools": old.get("auto_approve_tools", False),
            "system_instructions": old.get("system_instructions", DEFAULT_CONFIG["system_instructions"]),
            "reasoning": old.get("reasoning", "medium"),
        })
        
        # Mescla endpoints se existirem
        if "endpoints" in old:
            for ep_id, ep_data in old["endpoints"].items():
                if ep_id in new_config["endpoints"]:
                    new_config["endpoints"][ep_id].update(ep_data)
        
        # Mescla mcp_servers
        if "mcp_servers" in old:
            for srv_id, srv_data in old["mcp_servers"].items():
                if srv_id in new_config["mcp_servers"]:
                    new_config["mcp_servers"][srv_id].update(srv_data)
        
        # Mescla tools_config
        if "tools_config" in old:
            new_config["tools_config"].update(old["tools_config"])
        
        # Salva v2
        save_config(new_config)
        
        # Copia DB de sessões se existir
        if v1_db.exists() and not DB_FILE.exists():
            import shutil
            shutil.copy2(v1_db, DB_FILE)
        
        print(f"Migração v1 -> v2 concluida. Config: {CONFIG_FILE}, DB: {DB_FILE}")
        return True
    except Exception as e:
        print(f"Erro na migracao: {e}")
        return False


def set_api_key(provider: str, key: str) -> bool:
    """Armazena API key no OS keyring."""
    return set_api_key(provider, key)


def get_secret(keyring_name: str) -> Optional[str]:
    """Get secret from OS keyring by name."""
    try:
        return keyring.get_password(KEYRING_SERVICE, keyring_name)
    except Exception:
        return None


if __name__ == "__main__":
    # Teste rápido
    cfg = load_config()
    print(f"Provider: {cfg.get('default_provider')}")
    print(f"Model: {cfg.get('default_model')}")
    print(f"Theme: {cfg.get('theme')}")
    for prov in ["anthropic", "openai", "google"]:
        key = get_api_key(prov, cfg)
        print(f"  {prov}: {'***' if key else 'nao configurado'}")