# 🚀 OPUS AGENT - Pesquisa de Mercado & Roadmap Estratégico

## 1. Panorama Competitivo: O Estado da Arte dos AI Coding Agents

| Ferramenta | Stack | Pontos Fortes | Pontos Fracos / Dores |
| :--- | :--- | :--- | :--- |
| **Claude Code** (Anthropic) | Node/TypeScript | Raciocínio profundo, auto-compactação de contexto, bash execution seguro. | Preso ao ecossistema Node, pesado no Windows, layout fixo sem wizard customizável. |
| **Aider** | Python | Git-first (commits atômicos), Repo Map via Tree-sitter, benchmarks SWE-bench altos. | Visual austero/básico, curva de configuração manual complexa sem wizard moderno. |
| **Goose** (Block) | Rust / Python | Arquitetura 100% baseada no protocolo MCP, plugins dinâmicos. | Pouco amigável para customização visual, focado apenas em MCP genérico. |
| **Cursor / Windsurf** | Go / Electron | Indexação semântica do repositório, context rules (.cursorrules). | Dependente de IDE gráfica fechada; CLI secundária. |

---

## 2. Por que Python 100% Puro é Superior ao TypeScript/Node para esta CLI

1. **Adeus Dores de Cabeça no Windows**:
   - No ecossistema Node/TS, bibliotecas de terminal como React Ink sofrem com quebras de cursor, re-renders lentos, incompatibilidade com cmd/powershell legado e problemas de codepage (CP1252/UTF-8).
   - Python roda diretamente no terminal com inicialização instantânea e controle fino sobre codepages e streams.
2. **Design Terminal de Primeira Linha**:
   - Usando `Rich` e `Prompt Toolkit` em Python, obtemos animações, painéis, tabelas, destaques de sintaxe de dezenas de linguagens e compatibilidade cruzada sem travamentos.
3. **Ecossistema Nativo de IA**:
   - Python é a língua franca da Inteligência Artificial. Conectar com Ollama local, SDKs oficiais e ferramentas de sistema requer zero wrappers desnecessários.

---

## 3. Matriz de Funcionalidades do OPUS Agent

### A. Experiência de Usuário & Visual (Entregue na Fase 1)
- [x] **Banner Dinâmico com Gradiente Cyberpunk**: Informa em tempo real o provedor ativo, modelo, workspace atual e modo de segurança.
- [x] **Wizard Interativo Integrado (`/wizard`)**:
  - Seleção de Provedores (Claude, OpenAI, Gemini, Ollama, DeepSeek, Groq).
  - Gestor de Chaves de API com mascaramento seguro.
  - Catálogo Visual de Ferramentas Nativas e Servidores MCP.
  - Alternador de Modo de Segurança (Confirmação Prévia vs Auto-Aprovação).
  - Personalizador de Temas Visuais (Cyberpunk, Matrix, Slate, Sunset).
  - Teste de Diagnóstico e Latência em tempo real.
- [x] **Script Batch de Instalação e Execução (`run.bat` / `start.bat`)**:
  - Cria ambiente virtual `.venv` automaticamente.
  - Instala e valida dependências sem intervenção manual.
  - Dispara a ferramenta imediatamente.

### B. Próximos Passos de Execução
- [ ] **Streaming Token-a-Token**: Exibição fluida das respostas de IA com renderizador Markdown colorido.
- [ ] **Visualizador de Diffs Cirúrgicos**: Exibição em verde/vermelho antes de aplicar edições de código.
- [ ] **Executor Nativo de Comandos**: Execução assíncrona de comandos no shell com interrupção limpa por `Ctrl+C`.
- [ ] **Cliente MCP Completo**: Conexão com servidores MCP locais e remotos via stdio/SSE.
