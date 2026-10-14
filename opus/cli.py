"""OPUS Agent - Ponto de entrada da CLI (orquestrador fino)."""

import argparse
import sys

from rich.console import Console
from rich.text import Text

from .config import load_config, save_config
from .core.client import LLMError, chat, chat_stream  # noqa: F401  (chat_stream reservado)
from .core.session_store import SessionStore
from .core.vision import build_message, has_vision_support, read_image
from .core.planning import Plan, PlanStep, PlanStatus, StepStatus, PlanExecutor, create_plan, parse_plan_response, PLANNING_SYSTEM_PROMPT
from .ui.md_render import md_to_lines, render_blocks
from .ui.prompt_input import OpusInput, pipe_read, is_interactive_tty, GLYPH_PROMPT
from .ui.theme import build_rich_theme, GLYPH_PROMPT as THEME_GLYPH_PROMPT, clear_screen_full
from .ui.banner import render_banner
from .ui.statusbar import render_statusbar
from .ui.help_view import render_help
from .ui.sessions_view import render_sessions
from .ui.wizard import OpusWizard
from .ui.tools_viewer import render_tools_dashboard, render_tool_execution


def get_console(config: dict) -> Console:
    """Cria console com tema dinâmico baseado na config."""
    theme_id = config.get("theme", "cyberpunk_neon")
    return Console(theme=build_rich_theme(theme_id))


EXIT_WORDS = {"/exit", "/quit", "/sair", "exit", "quit", ":q"}


def parse_args():
    parser = argparse.ArgumentParser(
        prog="opus",
        description="OPUS Agent - assistente de codigo no terminal",
    )
    parser.add_argument("--wizard", action="store_true", help="abre a configuracao")
    parser.add_argument("--tools", action="store_true", help="lista ferramentas")
    parser.add_argument("-p", "--provider", type=str, help="provedor LLM ativo")
    parser.add_argument("-m", "--model", type=str, help="modelo LLM ativo")
    parser.add_argument("-y", "--yes", action="store_true", help="auto-aprova ferramentas")
    return parser.parse_args()


def render_home(config: dict) -> None:
    console = get_console(config)
    clear_screen_full(console)
    render_banner(console, config)
    render_statusbar(console, config)
    console.print()


def handle_plan_command(console, config, history, store, session_id, system_prompt, user_input):
    """Handle /plan command - create and execute multi-step plans."""
    from .core.planning import Plan, create_plan, parse_plan_response, PlanExecutor
    from .core.agent import run_agent
    from .core.exec import execute_tool
    
    # Extract goal from command
    if user_input == "/plan":
        goal = pipe_read("objetivo do plano").strip()
        if not goal:
            console.print(Text("  objetivo vazio", style="opus.warning"))
            return
    else:
        goal = user_input[6:].strip()  # Remove "/plan "
        if not goal:
            goal = pipe_read("objetivo do plano").strip()
            if not goal:
                console.print(Text("  objetivo vazio", style="opus.warning"))
                return
    
    console.print(Text(f"  🧠 Criando plano para: {goal}", style="opus.accent"))
    
    # Create plan via LLM
    plan_prompt = {
        "role": "system",
        "content": f"""Você é um planejador estratégico. Decomponha o objetivo em passos executáveis.

REGRAS:
1. Cada passo = UMA ação concreta e verificável
2. Passos independentes quando possível
3. Inclua ferramenta sugerida e argumentos
5. Outcome esperado mensurável
6. Máximo 10 passos

FORMATO JSON:
{{
  "goal": "objetivo claro",
  "steps": [
    {{
      "id": "step_1",
      "description": "descrição da ação",
      "tool": "nome_da_tool",
      "args": {{"arg": "valor"}},
      "expected_outcome": "resultado mensurável",
      "max_retries": 3
    }}
  ]
}}

FERRAMENTAS DISPONÍVEIS:
- read_file, write_file, edit_file, list_files
- search_code, ast_analyzer
- execute_command, git_integration
- web_search, web_browse
- mcp_filesystem_*
- ask_user (para esclarecimento)

OBJETIVO: {goal}

Retorne APENAS o JSON do plano."""
    }
    
    # Add planning prompt to history temporarily
    history.append(plan_prompt)
    
    from .core.client import chat
    try:
        result = chat(config, history, tools=None)
        plan_text = result.content
    except Exception as e:
        console.print(Text(f"  Erro ao criar plano: {e}", style="opus.error"))
        history.pop()  # Remove planning prompt
        return
    
    history.pop()  # Remove planning prompt
    
    # Parse plan
    plan = parse_plan_response(plan_text)
    if not plan:
        console.print(Text("  Falha ao parsear plano do LLM", style="opus.error"))
        return
    
    console.print(Text(f"  ✓ Plano criado com {len(plan.steps)} passos", style="opus.success"))
    for i, step in enumerate(plan.steps, 1):
        console.print(Text(f"  {i}. {step.description}", style="opus.muted"))
    
    # Confirm execution
    if not config.get("auto_approve_tools", False):
        confirm = pipe_read("Executar plano? [s/N]").strip().lower()
        if confirm != "s":
            console.print(Text("  Plano cancelado", style="opus.muted"))
            return
    
    # Execute plan
    from .core.agent import run_agent
    from .core.exec import execute_tool
    
    def ask_callback(question, confirm=False):
        label = f"  {question}" if not confirm else f"  {question}"
        console.print(Text(label, style="opus.warning"))
        if is_interactive_tty():
            from prompt_toolkit import PromptSession
            return PromptSession().prompt(f"  {GLYPH_PROMPT} ")
        sys.stdout.write(f"  {GLYPH_PROMPT} ")
        sys.stdout.flush()
        return pipe_read("", "")
    
    executor = PlanExecutor(
        execute_tool_fn=execute_tool,
        ask_callback=ask_callback,
        console=console,
        config=config,
    )
    
    console.print(Text("  ▶ Executando plano...", style="opus.accent"))
    plan = executor.execute(plan)
    
    # Show results
    if plan.status.value == "completed":
        console.print(Text("  ✓ Plano concluído com sucesso", style="opus.success"))
    else:
        console.print(Text(f"  ✗ Plano falhou: {plan.status.value}", style="opus.error"))
        for step in plan.steps:
            if step.status.value == "failed":
                console.print(Text(f"  ✗ {step.description}: {step.error}", style="opus.error"))
    
    # Save plan to session
    from .core.planning import save_plan
    save_plan(plan, store)


def interactive_session() -> None:
    config = load_config()
    console = get_console(config)
    render_home(config)

    system_prompt = config.get(
        "system_instructions",
        "Voce e o OPUS Agent, um assistente de codigo. Responda em pt-BR, direto.",
    )
    history: list = [{"role": "system", "content": system_prompt}]
    prompt = OpusInput()
    store = SessionStore()
    bootstrap_id = store.create()  # sessao vazia de bootstrap; some do /sessions se nao usada
    session_id = bootstrap_id

    while True:
        try:
            user_input = prompt.read().strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            break

        if not user_input:
            continue

        if user_input in EXIT_WORDS:
            console.print(Text("  ate a proxima.", style="opus.muted"))
            break
        elif user_input == "/ajuda":
            render_help(console)
        elif user_input in ("/wizard", "/config", "/settings"):
            config = OpusWizard(console, config).run()
            console = get_console(config)
            render_home(config)
        elif user_input in ("/tools", "/mcps"):
            render_tools_dashboard(console, config)
        elif user_input == "/model":
            config = OpusWizard(console, config).run()
            console = get_console(config)
            clear_screen_full(console)
            render_home(config)
        elif user_input == "/raciocinio":
            wizard = OpusWizard(console, config)
            wizard._menu_reasoning()
            save_config(config)
            console = get_console(config)
            clear_screen_full(console)
            render_home(config)
        elif user_input == "/sessions":
            render_sessions(console, store, session_id)
        elif user_input.startswith("/resume"):
            arg = user_input[len("/resume"):].strip()
            rows = store.list_sessions()
            target = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(rows):
                    target = rows[idx]
            elif arg:
                for r in rows:
                    if r["id"] == arg:
                        target = r
                        break
            if target:
                session_id = target["id"]
                history = [{"role": "system", "content": system_prompt}] + store.get_messages(session_id)
                console.print(Text(f"  sessao {session_id} carregada ({target['name'] or 'sem nome'})", style="opus.muted"))
                render_home(config)
                render_sessions(console, store, session_id)
            else:
                console.print(Text("  use: /resume <numero ou id> (veja /sessions)", style="opus.warning"))
        elif user_input == "/visao":
            source = pipe_read("imagem (caminho ou Enter p/ clipboard)").strip()
            data = read_image(source)
            if not data:
                console.print(Text("  sem imagem (caminho nao achou / clipboard vazio)", style="opus.error"))
            else:
                b, mime = data
                model = config.get("default_model", "")
                if not has_vision_support(model):
                    console.print(Text(f"  modelo '{model}' nao suporta visao", style="opus.error"))
                else:
                    q = pipe_read("pergunta (opcional)", "").strip()
                    msg = build_message(q or "Analise esta imagem.", b, mime)
                    history.append(msg)
                    if len(history) == 2:
                        store.ensure_name(session_id, "analise de imagem")
                    store.add_message(session_id, "user", q or "analise de imagem")
                    from .core.agent import run_agent
                    reply, err = run_agent(console, config, history, ask_callback=lambda *a, **k: "")
                    if err:
                        console.print(Text(f"  {err}", style="opus.error"))
                    elif reply:
                        store.add_message(session_id, "assistant", reply)
                        if not console.is_terminal:
                            from .ui.md_render import md_to_lines, render_blocks
                            render_blocks(console, md_to_lines(reply))
        elif user_input == "/plan":
            handle_plan_command(console, config, history, store, session_id, system_prompt, user_input)
        elif user_input.startswith("/plan "):
            handle_plan_command(console, config, history, store, session_id, system_prompt, user_input)
        elif user_input in ("/clear", "cls", "clear"):
            render_home(config)
        elif user_input.startswith("/"):
            console.print(
                Text.assemble(
                    ("  comando desconhecido: ", "opus.warning"),
                    (user_input, "opus.text"),
                    ("  (veja ", "opus.muted"),
                    ("/ajuda", "opus.accent"),
                    (")", "opus.muted"),
                )
            )
        else:
            if len(history) == 1:
                store.ensure_name(session_id, user_input)
            store.add_message(session_id, "user", user_input)
            history.append({"role": "user", "content": user_input})

            def ask(question, confirm=False):
                label = f"  {question}" if not confirm else f"  {question}"
                console.print(Text(label, style="opus.warning"))
                if is_interactive_tty():
                    from prompt_toolkit import PromptSession
                    return PromptSession().prompt(f"  {GLYPH_PROMPT} ")
                sys.stdout.write(f"  {GLYPH_PROMPT} ")
                sys.stdout.flush()
                return pipe_read("", "")

            from .core.agent import run_agent
            reply, err = run_agent(console, config, history, ask_callback=ask)
            if err:
                console.print(Text(f"  {err}", style="opus.error"))
                history.pop()
            elif reply:
                store.add_message(session_id, "assistant", reply)
                if not console.is_terminal:
                    from .ui.md_render import md_to_lines, render_blocks
                    render_blocks(console, md_to_lines(reply))
        console.print()


def main() -> None:
    args = parse_args()
    config = load_config()
    console = get_console(config)

    if args.provider:
        config["default_provider"] = args.provider
        save_config(config)
    if args.model:
        config["default_model"] = args.model
        save_config(config)
    if args.yes:
        config["auto_approve_tools"] = True
        save_config(config)

    if args.wizard:
        OpusWizard(console, config).run()
        return
    if args.tools:
        render_tools_dashboard(console, config)
        return

    interactive_session()


if __name__ == "__main__":
    main()
