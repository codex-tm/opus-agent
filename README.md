# ⚡ OPUS Agent - Assistente Autônomo de Código CLI (Pure Python)

> Ferramenta de linha de comando 100% construída em Python, inspirada no Claude Code, com design visual de ponta, sistema de skills extensível, MCP (Model Context Protocol) nativo, e distribuição standalone via PyInstaller.

---

## 🚀 Início Rápido

### Opção 1: Executável Standalone (Recomendado)
```bash
# Baixe o opus.exe do release mais recente
# Ou build local:
python installer.py --build
./dist/opus.exe
```

### Opção 2: Desenvolvimento (com venv)
```bash
git clone https://github.com/codex-tm/opus-agent.git
cd opus-agent
python installer.py --dev
python main.py
```

### Opção 3: Scripts Batch (Windows)
```cmd
run.bat           # Modo interativo
run.bat --wizard  # Configuração
run.bat --tools   # Lista ferramentas
```

---

## 📦 O que vem no pacote

### Core Features
- **Chat interativo** com streaming, reasoning, tools
- **Configuração TOML + Keyring** (Windows Credential Manager / Linux Secret Service / macOS Keychain)
- **Sessões SQLite + FTS5** com busca full-text, export/import JSON/Markdown/HTML
- **MCP Client nativo** - JSON-RPC 2.0 over stdio, 4 servidores built-in
- **Agent Loop robusto** - Circuit breaker, exponential backoff, planejamento multi-step (`/plan`)

### 14 Skills Built-in (106 tools, 98 hooks)

| Skill | Tools | Descrição |
|-------|-------|-----------|
| **code-review** | 5 | Lint (ruff/pylint), security scan (bandit/semgrep), complexity, review, diff analysis |
| **command-palette** | 8 | Fuzzy search para comandos, skills, tools, arquivos |
| **deploy** | 10 | PyInstaller, Docker, NSIS installer, GitHub release, PyPI, changelog |
| **diff-viewer** | 7 | Unified/inline/side-by-side diff, git diff, export HTML/MD/patch |
| **doc-writer** | 7 | README, API docs, changelog, ADR, diagrams (Mermaid/PlantUML), MkDocs site |
| **file-watcher** | 10 | Glob/regex patterns, debouncing, auto-test/build/reload |
| **git-workflow** | 10 | Branch, commit, PR, sync, cleanup |
| **mcp-connection** | 6 | Gerencia servidores MCP, descoberta de tools |
| **notifications** | 12 | Desktop, webhook, email, Telegram, Slack, Discord, Pushover, ntfy |
| **progress-bars** | 6 | Progress bars, spinners, status indicators Rich |
| **refactor-helper** | 7 | Extract method/class, rename, move, interface, preview/apply |
| **session-manager** | 12 | Branching, merging, search, export/import, stats |
| **skill-installer** | 7 | Create, install, remove, update, test skills |
| **test-generator** | 7 | Unit, integration, property, e2e, coverage, fixtures |

### 4 MCP Servers Built-in
| Servidor | Comando | Descrição |
|----------|---------|-----------|
| filesystem | `python -m opus.mcp.fs` | Acesso seguro ao sistema de arquivos |
| github | `python -m opus.mcp.servers.github` | GitHub API (precisa GITHUB_TOKEN) |
| postgresql | `python -m opus.mcp.servers.postgresql` | PostgreSQL (precisa connection string) |
| brave | `python -m opus.mcp.servers.brave` | Brave Search (precisa BRAVE_API_KEY) |

---

## 🛠️ Comandos Principais

### CLI Flags
```bash
opus.exe                    # Modo interativo
opus.exe --wizard           # Config wizard
opus.exe --tools            # Lista tools + MCPs
opus.exe -p anthropic -m claude-3-5-sonnet-20241022
opus.exe -y                 # Auto-aprova tools
```

### Comandos Interativos
| Comando | Descrição |
|---------|-----------|
| `/help` | Lista todos os comandos |
| `/wizard` | Central de configuração visual |
| `/tools` | Dashboard de ferramentas (Rich Tables) |
| `/model` | Troca provider/modelo |
| `/plan` | Cria e executa plano multi-step |
| `/sessions` | Lista/resume sessões |
| `/mcp` | Gerencia servidores MCP |
| `/palette` | Command palette (fuzzy search) |
| `/clear` | Limpa tela (scrollback clear) |
| `/exit` | Sai do agente |

---

## ⚙️ Configuração

### Arquivo: `%LOCALAPPDATA%\opus\config_v2\config.toml`
```toml
theme = "cyberpunk_neon"
default_provider = "anthropic"
default_model = "claude-3-5-sonnet-20241022"
auto_approve_tools = false

[endpoints.anthropic]
base_url = "https://api.anthropic.com/v1"
default_model = "claude-3-5-sonnet-20241022"
enabled = true

# ... openai, google, deepseek, groq, ollama, openrouter
```

### API Keys (OS Keyring - NÃO no arquivo)
```bash
# Windows: Credential Manager
# Linux: secretstorage (DBus)
# macOS: Keychain

# Via CLI ou wizard
opus.exe --wizard  # aba Security > API Keys
```

### MCP Servers: `%LOCALAPPDATA%\opus\config_v2\mcp\servers.toml`
```toml
[servers.filesystem]
command = "python -m opus.mcp.fs"
enabled = true

[servers.github]
command = "python -m opus.mcp.servers.github"
enabled = false  # Precisa GITHUB_TOKEN no keyring
```

---

## 🏗️ Build & Distribuição

### PyInstaller (Standalone EXE)
```bash
python installer.py --build
# Output: dist/opus.exe (~54 MB)
```

### NSIS Installer (Windows)
```bash
# Precisa NSIS instalado
python installer.py --installer
# Output: OPUS-Agent-1.0.0-Setup.exe
```

### Docker
```bash
docker build -t opus-agent .
docker run -it -v %LOCALAPPDATA%/opus:/root/.opus opus-agent
```

### GitHub Release
```bash
python -c "from opus.skills.deploy.tools import deploy_release; deploy_release('1.0.0', 'Release notes')"
```

---

## 🧪 Testes

```bash
# Todos os smoke tests
for f in tests/smoke_*.py; do python "$f"; done

# 14/14 tests passing:
# smoke_agent, smoke_agent_loop, smoke_browser, smoke_reasoning,
# smoke_reasoning_payload, smoke_sessions, smoke_stream,
# smoke_stream_render, smoke_stream_tool_format, smoke_stream_tools,
# smoke_thinking, smoke_vision, smoke_visual, smoke_wizard
```

---

## 📁 Estrutura do Projeto

```
opus-agent/
├── main.py                 # Entry point
├── installer.py            # Instalador completo (--dev/--build/--installer/--verify)
├── requirements.txt        # Dependências Python
├── run.bat / start.bat     # Scripts Windows
├── opus/
│   ├── cli.py              # CLI principal, comandos, render_home
│   ├── config_v2.py        # TOML + Keyring config
│   ├── session_store_v2.py # SQLite + FTS5 sessions
│   ├── mcp_client.py       # JSON-RPC 2.0 MCP client/manager
│   ├── skills_registry.py  # Skill discovery, loading, hooks
│   ├── core/
│   │   ├── agent.py        # Agent loop, circuit breaker, planning
│   │   ├── exec.py         # Tool execution + MCP integration
│   │   ├── tools.py        # 13 native tools
│   │   └── browser.py      # Playwright web browse
│   ├── mcp/
│   │   ├── fs.py           # Filesystem MCP server
│   │   └── servers/        # GitHub, PostgreSQL, Brave MCP servers
│   ├── ui/
│   │   ├── theme.py        # Themes, glyphs, clear_screen_full
│   │   ├── wizard.py       # Config wizard
│   │   ├── tools_viewer.py # Tools dashboard
│   │   ├── prompt_input.py # TTY-aware input
│   │   └── select.py       # Arrow menu selection
│   └── config_v2/skills/   # 14 built-in skills (source)
└── tests/
    └── smoke_*.py          # 14 smoke tests
```

---

## 🔧 Desenvolvimento

### Adicionar Nova Skill
```bash
# Via skill-installer skill
opus.exe
> /tools  # ou skill_create
> skill_create "minha-skill"
```

Estrutura gerada:
```
~/.opus/config_v2/skills/minha-skill/
├── SKILL.md      # Metadados (name, version, description, tools, hooks)
├── tools.py      # TOOLS dict com funções
└── hooks.py      # pre_tool_call, post_tool_call, etc.
```

### Adicionar MCP Server
1. Criar `opus/mcp/meu_server.py` com classe `MCPServer`
2. Registrar em `servers.toml`
3. Reiniciar - tools ficam disponíveis como `mcp_meu_server_tool_name`

---

## 🎨 Temas Disponíveis
- `cyberpunk_neon` (padrão) - Verde/ciano neon
- `slate_professional` - Cinza/azul corporativo
- `dracula` - Roxo/rosa Dracula theme
- `monokai` - Clássico Monokai

---

## 📋 Requisitos

- **Python 3.11+** (testado em 3.11, 3.12, 3.13, 3.14)
- **Windows 10/11**, Linux, macOS
- **Playwright browsers** (instalados via `installer.py --dev` ou `playwright install`)
- **NSIS** (opcional, para criar installer Windows)

---

## 📄 Licença

MIT License - veja [LICENSE](LICENSE)

---

## 🤝 Contribuindo

1. Fork o repo
2. Crie branch: `git checkout -b feature/nova-feature`
3. Commit: `git commit -m "feat: adiciona nova feature"`
4. Push: `git push origin feature/nova-feature`
5. Abra PR

---

## 🔗 Links

- **Repo**: https://github.com/codex-tm/opus-agent
- **Issues**: https://github.com/codex-tm/opus-agent/issues
- **Releases**: https://github.com/codex-tm/opus-agent/releases

---

*Built with ❤️ using Python, Rich, Prompt Toolkit, Playwright, and 14 extensible skills.*
