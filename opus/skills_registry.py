import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from importlib.util import spec_from_file_location, module_from_spec


def _get_config_base_dir() -> Path:
    """Get base config directory (LOCALAPPDATA on Windows, ~/.opus on Unix)."""
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "opus" / "config_v2"
    return Path.home() / ".opus" / "config_v2"


@dataclass
class Skill:
    """Represents a skill with its metadata and components."""
    name: str
    path: Path
    metadata: Dict[str, Any]
    tools: Dict[str, Callable] = field(default_factory=dict)
    hooks: Dict[str, Callable] = field(default_factory=dict)
    tools_module: Any = None
    hooks_module: Any = None


class SkillRegistry:
    """Registry for discovering, loading, and managing skills."""
    
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.config_base_dir = _get_config_base_dir()
        self.system_skills_path = self.config_base_dir / "skills"
        self.global_skills_path = Path.home() / ".agnts"
        self.hooks: Dict[str, List[Callable]] = {
            "pre_tool_call": [],
            "post_tool_call": [],
            "pre_llm_call": [],
            "post_llm_call": [],
            "on_error": [],
            "on_session_start": [],
            "on_session_end": [],
        }
    
    def discover(self, paths: Optional[List[Path]] = None) -> List[Skill]:
        """Discover skills in given paths."""
        if paths is None:
            paths = []
            if self.system_skills_path.exists():
                paths.append(self.system_skills_path)
            if self.global_skills_path.exists():
                paths.append(self.global_skills_path)
        
        discovered = []
        for base_path in paths:
            if not base_path.exists():
                continue
            for skill_dir in base_path.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                skill = self._load_skill(skill_dir, skill_file)
                if skill:
                    discovered.append(skill)
        
        return discovered
    
    def _load_skill(self, skill_dir: Path, skill_file: Path) -> Optional[Skill]:
        """Load a skill from its directory."""
        try:
            # Parse SKILL.md frontmatter
            content = skill_file.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return None
            
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None
            
            import yaml
            metadata = yaml.safe_load(parts[1])
            
            skill = Skill(
                name=metadata.get("name", skill_dir.name),
                path=skill_dir,
                metadata=metadata,
            )
            
            # Load tools.py if exists
            tools_file = skill_dir / "tools.py"
            if tools_file.exists():
                skill.tools_module = self._load_module(tools_file, f"skill_{skill.name}_tools")
                # Extract tools dict
                if hasattr(skill.tools_module, "TOOLS"):
                    skill.tools = skill.tools_module.TOOLS
            
            # Load hooks.py if exists
            hooks_file = skill_dir / "hooks.py"
            if hooks_file.exists():
                skill.hooks_module = self._load_module(hooks_file, f"skill_{skill.name}_hooks")
                # Register hooks - populate both skill.hooks and registry.hooks
                for hook_name in self.hooks:
                    if hasattr(skill.hooks_module, hook_name):
                        hook_func = getattr(skill.hooks_module, hook_name)
                        skill.hooks[hook_name] = hook_func
                        self.hooks[hook_name].append(hook_func)
            
            self.skills[skill.name] = skill
            return skill
            
        except Exception as e:
            print(f"Error loading skill {skill_dir}: {e}")
            return None
    
    def _load_module(self, file_path: Path, module_name: str):
        """Load a Python module from file."""
        spec = spec_from_file_location(module_name, file_path)
        if spec and spec.loader:
            module = module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        return None
    
    def register(self, skill: Skill) -> None:
        """Register a skill."""
        self.skills[skill.name] = skill
        # Register hooks
        for hook_name, hooks in skill.hooks.items():
            if hook_name in self.hooks:
                self.hooks[hook_name].extend(hooks)
    
    def install(self, source: str, target: str = "system") -> Optional[Skill]:
        """Install a skill from source (git URL, local path, or registry name)."""
        target_path = self.system_skills_path if target == "system" else self.global_skills_path
        target_path.mkdir(parents=True, exist_ok=True)
        
        skill_dir = target_path / source.split("/")[-1].replace(".git", "")
        
        if source.startswith("http://") or source.startswith("https://") or source.startswith("git@"):
            # Git clone
            try:
                subprocess.run(["git", "clone", source, str(skill_dir)], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to clone skill: {e}")
                return None
        elif Path(source).exists():
            # Local copy
            import shutil
            shutil.copytree(source, skill_dir, dirs_exist_ok=True)
        else:
            print(f"Unknown skill source: {source}")
            return None
        
        return self._load_skill(skill_dir, skill_dir / "SKILL.md")
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool by name from any skill."""
        for skill in self.skills.values():
            if name in skill.tools:
                return skill.tools[name]
        return None
    
    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all tools from all skills."""
        tools = {}
        for skill in self.skills.values():
            tools.update(skill.tools)
        return tools
    
    def trigger_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Trigger all hooks of a given type."""
        results = []
        for hook in self.hooks.get(hook_name, []):
            try:
                result = hook(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"Hook {hook_name} error: {e}")
        return results
    
    def load_all(self) -> int:
        """Load all skills from default paths."""
        skills = self.discover()
        print(f"Loaded {len(skills)} skills")
        return len(skills)


# Global registry instance
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get global skill registry."""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
        _skill_registry.load_all()
    return _skill_registry


def create_skill_structure(skill_name: str, target: str = "system") -> Path:
    """Create a new skill directory structure."""
    target_path = Path.home() / (".opus/skills" if target == "system" else ".agnts")
    skill_dir = target_path / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    # SKILL.md template
    (skill_dir / "SKILL.md").write_text(f"""---
name: {skill_name}
version: 1.0.0
description: Skill description here
author: Your Name
category: utility
tags: []
---

# {skill_name}

Skill description.

## Tools

List tools here.

## Hooks

List hooks here.
""", encoding="utf-8")
    
    # tools.py template
    (skill_dir / "tools.py").write_text(f'''"""
{skill_name} - Custom tools.
"""

TOOLS = {{
    # "tool_name": tool_function,
}}

def example_tool(param: str) -> str:
    """Example tool."""
    return f"Result: {{param}}"

# TOOLS["example_tool"] = example_tool
''', encoding="utf-8")
    
    # hooks.py template
    (skill_dir / "hooks.py").write_text(f'''"""
{skill_name} - Agent loop hooks.
"""

def pre_tool_call(tool_name: str, args: dict) -> dict:
    """Called before tool execution. Return modified args or None."""
    return args

def post_tool_call(tool_name: str, result: dict) -> dict:
    """Called after tool execution. Return modified result or None."""
    return result

def pre_llm_call(messages: list, tools: list) -> tuple:
    """Called before LLM call. Return (messages, tools) or None."""
    return None

def post_llm_call(response: any) -> any:
    """Called after LLM call. Return modified response or None."""
    return None

def on_error(error: Exception, context: dict):
    """Called on any error."""
    pass

def on_session_start(session_id: str, config: dict):
    """Called when session starts."""
    pass

def on_session_end(session_id: str, history: list):
    """Called when session ends."""
    pass
''', encoding="utf-8")
    
    return skill_dir


if __name__ == "__main__":
    registry = SkillRegistry()
    skills = registry.discover()
    for skill in skills:
        print(f"Skill: {skill.name} - {skill.metadata.get('description', '')}")
        print(f"  Tools: {list(skill.tools.keys())}")
        print(f"  Hooks: {list(skill.hooks.keys())}")