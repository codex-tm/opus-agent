"""
OPUS Agent v2 - Planning System.

Multi-step planning with execution, review, and adjustment.
"""

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


class PlanStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """Single step in a plan."""
    id: str
    description: str
    tool: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retries: int = 0
    max_retries: int = 3


@dataclass
class Plan:
    """Multi-step execution plan."""
    id: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [asdict(s) for s in self.steps],
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        plan = cls(
            id=data["id"],
            goal=data["goal"],
            status=PlanStatus(data.get("status", "pending")),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )
        plan.steps = [
            PlanStep(
                id=s["id"],
                description=s["description"],
                tool=s.get("tool"),
                args=s.get("args", {}),
                expected_outcome=s.get("expected_outcome", ""),
                status=StepStatus(s.get("status", "pending")),
                result=s.get("result"),
                error=s.get("error"),
                started_at=s.get("started_at"),
                completed_at=s.get("completed_at"),
                retries=s.get("retries", 0),
                max_retries=s.get("max_retries", 3),
            )
            for s in data.get("steps", [])
        ]
        return plan


PLANNING_SYSTEM_PROMPT = """Você é um planejador estratégico. Sua tarefa é decompor objetivos complexos em passos executáveis.

REGRAS:
1. Cada passo deve ser UMA ação concreta e verificável
2. Passos devem ser independentes quando possível (paralelizáveis)
3. Inclua ferramenta sugerida e argumentos esperados
4. Defina outcome esperado mensurável
5. Máximo 10 passos por plano
6. Se objetivo for vago, peça esclarecimento

FORMATO DE SAÍDA (JSON):
{
  "goal": "objetivo claro",
  "steps": [
    {
      "id": "step_1",
      "description": "descrição da ação",
      "tool": "nome_da_tool",
      "args": {"arg": "valor"},
      "expected_outcome": "resultado mensurável",
      "max_retries": 3
    }
  ]
}

FERRAMENTAS DISPONÍVEIS:
- read_file, write_file, edit_file, list_files
- search_code, ast_analyzer
- execute_command, git_integration
- web_search, web_browse
- mcp_filesystem_*
- ask_user (para esclarecimento)

EXEMPLO:
Goal: "Criar API REST com FastAPI"
Steps:
1. {id: "step_1", description: "Criar estrutura do projeto", tool: "execute_command", args: {"command": "mkdir -p api/{routes,models,schemas}"}, expected_outcome: "Diretórios criados"}
2. {id: "step_2", description: "Criar main.py com FastAPI", tool: "write_file", args: {"filepath": "api/main.py", "content": "..."}, expected_outcome: "Arquivo criado com app FastAPI"}
...
"""


def create_plan(goal: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Prompt para o LLM criar plano. Retorna dict com goal e steps."""
    ctx = context or {}
    available_tools = ctx.get("available_tools", [])
    
    prompt = f"""{PLANNING_SYSTEM_PROMPT}

CONTEXTO ADICIONAL:
{json.dumps(ctx, ensure_ascii=False, indent=2)}

FERRAMENTAS DISPONÍVEIS NESTA SESSÃO:
{", ".join(available_tools) if available_tools else "Todas"}

OBJETIVO: {goal}

Retorne APENAS o JSON do plano."""
    
    return {
        "role": "system",
        "content": prompt
    }


def parse_plan_response(response: str) -> Optional[Plan]:
    """Parse LLM response into Plan object."""
    try:
        # Extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            data = json.loads(json_str)
            
            plan_id = f"plan_{int(time.time() * 1000)}"
            plan = Plan(id=plan_id, goal=data.get("goal", ""))
            
            for i, step_data in enumerate(data.get("steps", [])):
                step = PlanStep(
                    id=step_data.get("id", f"step_{i+1}"),
                    description=step_data.get("description", ""),
                    tool=step_data.get("tool"),
                    args=step_data.get("args", {}),
                    expected_outcome=step_data.get("expected_outcome", ""),
                    max_retries=step_data.get("max_retries", 3),
                )
                plan.steps.append(step)
            
            return plan
    except Exception as e:
        print(f"Error parsing plan: {e}")
    
    return None


class PlanExecutor:
    """Executes a plan step by step with review and adjustment."""
    
    def __init__(
        self,
        execute_tool_fn: Callable,
        ask_callback: Callable,
        console,
        config: Dict[str, Any],
        on_step_complete: Optional[Callable] = None,
        on_step_failed: Optional[Callable] = None,
    ):
        self.execute_tool = execute_tool_fn
        self.ask_callback = ask_callback
        self.console = console
        self.config = config
        self.on_step_complete = on_step_complete
        self.on_step_failed = on_step_failed
        self.current_plan: Optional[Plan] = None
    
    def execute(self, plan: Plan) -> Plan:
        """Execute plan step by step."""
        self.current_plan = plan
        plan.status = PlanStatus.IN_PROGRESS
        plan.updated_at = time.time()
        
        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
            
            # Check if plan was cancelled
            if plan.status == PlanStatus.FAILED:
                break
            
            # Execute step
            step_result = self._execute_step(step)
            step.result = step_result
            
            if step_result.get("ok", False):
                step.status = StepStatus.COMPLETED
                step.completed_at = time.time()
                if self.on_step_complete:
                    self.on_step_complete(step)
            else:
                step.status = StepStatus.FAILED
                step.error = step_result.get("error", "Unknown error")
                if self.on_step_failed:
                    self.on_step_failed(step)
                
                # Retry logic
                if step.retries < step.max_retries:
                    step.retries += 1
                    step.status = StepStatus.PENDING
                    continue
                else:
                    plan.status = PlanStatus.FAILED
                    break
            
            plan.updated_at = time.time()
        
        if plan.status == PlanStatus.IN_PROGRESS:
            # Check if all steps completed
            if all(s.status == StepStatus.COMPLETED for s in plan.steps):
                plan.status = PlanStatus.COMPLETED
                plan.completed_at = time.time()
        
        return plan
    
    def _execute_step(self, step: PlanStep) -> Dict[str, Any]:
        """Execute a single step."""
        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        
        # Auto-approve for plan execution (configurable)
        auto_approve = True  # Could be config option
        
        # Import here to avoid circular
        from .exec import execute_tool
        
        try:
            if step.tool:
                # Execute with provided args - map common param names
                args = dict(step.args)
                
                # Map common parameter names to expected ones
                if step.tool in ("read_file", "write_file", "edit_file", "ast_analyzer"):
                    if "path" in args and "filepath" not in args:
                        args["filepath"] = args.pop("path")
                if step.tool == "list_files":
                    if "path" in args and "directory" not in args:
                        args["directory"] = args.pop("path")
                if step.tool == "execute_command":
                    if "cmd" in args and "command" not in args:
                        args["command"] = args.pop("cmd")
                if step.tool == "search_code":
                    if "pattern" in args and "query" not in args:
                        args["query"] = args.pop("pattern")
                
                # Execute with mapped args
                print(f"DEBUG: Executing tool {step.tool} with args {args}", file=sys.stderr)
                output = execute_tool(step.tool, args, Path.cwd(), {})
                print(f"DEBUG: Tool output: {output}", file=sys.stderr)
                result = json.loads(output) if isinstance(output, str) else output
                print(f"DEBUG: Parsed result: {result}", file=sys.stderr)
                return result
            else:
                # No tool specified - this is a reasoning step
                return {"ok": True, "result": "Step completed (no tool)"}
        except Exception as e:
            import traceback
            print(f"DEBUG: Exception in _execute_step: {e}\n{traceback.format_exc()}", file=sys.stderr)
            return {"ok": False, "error": str(e)}


def save_plan(plan: Plan, session_store) -> None:
    """Save plan to session metadata."""
    session_id = getattr(session_store, "current_session_id", None)
    if session_id:
        session_store.add_message(
            session_id, 
            "system", 
            f"PLAN:{plan.id}:{json.dumps(plan.to_dict())}"
        )


def load_plan(session_store, plan_id: str) -> Optional[Plan]:
    """Load plan from session."""
    # Implementation depends on session_store structure
    return None