#!/usr/bin/env python3
"""
OPUS Agent - Comprehensive Installer Script
Installs all dependencies, Playwright browsers, sets up config, copies skills.
Run with: python installer.py [--dev|--build|--install|--global]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import winreg
from pathlib import Path


REQUIREMENTS = [
    "rich>=13.7.0",
    "prompt_toolkit>=3.0.40",
    "requests>=2.31.0",
    "colorama>=0.4.6",
    "pydantic>=2.0.0",
    "Pillow>=10.0",
    "playwright>=1.40",
    "keyring>=25.0.0",
    "tomli-w>=1.0.0",
    "httpx>=0.27.0",
    "watchdog>=6.0.0",
    "PyYAML>=6.0",
]

PLAYWRIGHT_BROWSERS = ["chromium", "firefox", "webkit"]

SKILLS_SOURCE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".opus")) / "opus" / "config_v2" / "skills"
USER_CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".opus")) / "opus" / "config_v2"
USER_SKILLS_DIR = USER_CONFIG_DIR / "skills"

# Global install paths
GLOBAL_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".opus")) / "opus" / "bin"
GLOBAL_CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".opus")) / "opus" / "config_v2"


def run_cmd(cmd, cwd=None, capture=True):
    """Run command and return result."""
    print(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True, timeout=300)
        if result.returncode != 0 and capture:
            print(f"    stderr: {result.stderr.strip()}")
        return result.returncode == 0, result.stdout if capture else "", result.stderr if capture else ""
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT")
        return False, "", "timeout"
    except Exception as e:
        print(f"    ERROR: {e}")
        return False, "", str(e)


def install_python_deps():
    """Install Python dependencies from requirements.txt."""
    print("\n[1/6] Installing Python dependencies...")
    
    # Check pip
    ok, _, _ = run_cmd([sys.executable, "-m", "pip", "--version"])
    if not ok:
        print("  ERROR: pip not available")
        return False
    
    # Install each requirement
    for req in REQUIREMENTS:
        ok, _, _ = run_cmd([sys.executable, "-m", "pip", "install", req])
        if not ok:
            print(f"  WARNING: Failed to install {req}")
    
    # Also install from requirements.txt if exists
    req_file = Path(__file__).parent / "requirements.txt"
    if req_file.exists():
        ok, _, _ = run_cmd([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
        if not ok:
            print("  WARNING: Failed to install from requirements.txt")
    
    return True


def install_playwright_browsers():
    """Install Playwright browsers."""
    print("\n[2/6] Installing Playwright browsers...")
    
    ok, _, _ = run_cmd([sys.executable, "-m", "playwright", "install", "--with-deps"] + PLAYWRIGHT_BROWSERS)
    if not ok:
        print("  WARNING: Playwright browser install had issues (may need admin for --with-deps)")
        # Try without deps
        ok, _, _ = run_cmd([sys.executable, "-m", "playwright", "install"] + PLAYWRIGHT_BROWSERS)
    
    # Verify
    for browser in PLAYWRIGHT_BROWSERS:
        ok, out, _ = run_cmd([sys.executable, "-m", "playwright", "install", browser, "--dry-run"])
        if ok:
            print(f"  ✓ {browser} ready")
    
    return True


def setup_config_directories():
    """Create config directory structure."""
    print("\n[3/6] Setting up config directories...")
    
    dirs = [
        USER_CONFIG_DIR,
        USER_SKILLS_DIR,
        USER_CONFIG_DIR / "mcp",
        USER_CONFIG_DIR / "sessions",
        USER_CONFIG_DIR / "cache",
        USER_CONFIG_DIR / "logs",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {d}")
    
    return True


def copy_skills():
    """Verify skills exist in user config directory."""
    print("\n[4/6] Verifying skills...")
    
    if not USER_SKILLS_DIR.exists():
        print(f"  WARNING: Skills directory not found at {USER_SKILLS_DIR}")
        return False
    
    skill_count = 0
    for skill_dir in USER_SKILLS_DIR.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            print(f"  ✓ {skill_dir.name}")
            skill_count += 1
    
    print(f"  Total: {skill_count} skills verified")
    return skill_count > 0


def create_default_config():
    """Create default config.toml if not exists."""
    print("\n[5/6] Creating default config...")
    
    config_file = USER_CONFIG_DIR / "config.toml"
    if config_file.exists():
        print(f"  Config already exists: {config_file}")
        return True
    
    # Generate default config
    default_config = f"""version = "2.0.0"
theme = "cyberpunk_neon"
default_provider = "anthropic"
default_model = "claude-3-5-sonnet-20241022"
auto_approve_tools = false
system_instructions = "Voce e o OPUS Agent, um engenheiro de software autonomo de nivel senior."

[endpoints.anthropic]
name = "Anthropic Claude Official"
base_url = "https://api.anthropic.com/v1"
default_model = "claude-3-5-sonnet-20241022"
enabled = true

[endpoints.openai]
name = "OpenAI Official"
base_url = "https://api.openai.com/v1"
default_model = "gpt-4o"
enabled = true

[endpoints.google]
name = "Google Gemini"
base_url = "https://generativelanguage.googleapis.com/v1beta"
default_model = "gemini-2.0-flash"
enabled = true

[endpoints.deepseek]
name = "DeepSeek API"
base_url = "https://api.deepseek.com/v1"
default_model = "deepseek-coder"
enabled = true

[endpoints.groq]
name = "Groq Ultra Fast"
base_url = "https://api.groq.com/openai/v1"
default_model = "llama-3.3-70b-versatile"
enabled = true

[endpoints.ollama]
name = "Ollama Local"
base_url = "http://localhost:11434/v1"
default_model = "llama3.1:latest"
enabled = true

[endpoints.openrouter]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
default_model = "anthropic/claude-3.5-sonnet"
enabled = true

[mcp_servers.filesystem]
name = "Local Filesystem Server"
command = "python -m opus.mcp.fs"
enabled = true
description = "Acesso seguro e restrito ao diretorio do projeto."

[tools_config]
file_operations = true
terminal_execution = true
search_code = true
web_fetch = true
git_integration = true
ast_analysis = true
web_search = true
"""
    
    config_file.write_text(default_config, encoding="utf-8")
    print(f"  ✓ Created: {config_file}")
    return True


def create_mcp_servers_config():
    """Create MCP servers config."""
    print("\n[5b/6] Creating MCP servers config...")
    
    mcp_config = USER_CONFIG_DIR / "mcp" / "servers.toml"
    if mcp_config.exists():
        print(f"  MCP config already exists")
        return True
    
    mcp_content = """[servers.filesystem]
name = "Local Filesystem Server"
command = "python -m opus.mcp.fs"
enabled = true
description = "Acesso seguro e restrito ao diretorio do projeto."
env = {{}}

[servers.github]
name = "GitHub MCP Server"
command = "python -m opus.mcp.servers.github"
enabled = false
description = "GitHub API integration (requires GITHUB_TOKEN in keyring)"
env = {{}}

[servers.postgresql]
name = "PostgreSQL MCP Server"
command = "python -m opus.mcp.servers.postgresql"
enabled = false
description = "PostgreSQL database access (requires POSTGRES_CONNECTION_STRING in keyring)"
env = {{}}

[servers.brave]
name = "Brave Search MCP Server"
command = "python -m opus.mcp.servers.brave"
enabled = false
description = "Brave Search API (requires BRAVE_API_KEY in keyring)"
env = {{}}
"""
    
    mcp_config.write_text(mcp_content, encoding="utf-8")
    print(f"  ✓ Created: {mcp_config}")
    return True


def verify_installation():
    """Verify installation works."""
    print("\n[6/6] Verifying installation...")
    
    # Test imports
    test_imports = [
        "opus.cli",
        "opus.config_v2",
        "opus.session_store_v2",
        "opus.mcp_client",
        "opus.core.agent",
        "opus.core.exec",
        "opus.core.tools",
        "opus.core.browser",
        "opus.ui.theme",
        "opus.ui.wizard",
        "opus.ui.tools_viewer",
        "opus.skills_registry",
        "rich",
        "prompt_toolkit",
        "playwright",
        "keyring",
        "tomllib",
        "tomli_w",
        "httpx",
        "watchdog",
        "yaml",
    ]
    
    failed = []
    for mod in test_imports:
        ok, _, _ = run_cmd([sys.executable, "-c", f"import {mod}"])
        if ok:
            print(f"  ✓ {mod}")
        else:
            print(f"  ✗ {mod}")
            failed.append(mod)
    
    # Test Playwright
    ok, _, _ = run_cmd([sys.executable, "-c", "from playwright.sync_api import sync_playwright; print('Playwright OK')"])
    if ok:
        print("  ✓ Playwright functional")
    else:
        print("  ✗ Playwright not functional")
        failed.append("playwright-functional")
    
    # Test skills registry
    ok, out, _ = run_cmd([sys.executable, "-c", "from opus.skills_registry import get_skill_registry; r=get_skill_registry(); print(f'Skills: {len(r.skills)}')"])
    if ok:
        print(f"  ✓ Skills registry: {out.strip()}")
    else:
        print("  ✗ Skills registry failed")
        failed.append("skills-registry")
    
    if failed:
        print(f"\n  WARNING: {len(failed)} checks failed: {', '.join(failed)}")
        return False
    
    print("\n  ✓ All verification checks passed!")
    return True


def build_executable():
    """Build PyInstaller executable."""
    print("\n[BUILD] Building PyInstaller executable...")
    
    ok, _, _ = run_cmd([sys.executable, "-m", "pip", "install", "pyinstaller"])
    if not ok:
        print("  ERROR: Failed to install PyInstaller")
        return False
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--onefile",
        "--console",
        "--name", "opus",
        "--add-data", f"{USER_CONFIG_DIR};opus/config_v2",
        "--hidden-import", "keyring",
        "--hidden-import", "keyring.backends.Windows",
        "--hidden-import", "tomllib",
        "--hidden-import", "tomli_w",
        "--hidden-import", "rich",
        "--hidden-import", "prompt_toolkit",
        "--hidden-import", "sqlite3",
        "--hidden-import", "httpx",
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "PIL",
        "--exclude-module", "tkinter",
        "--exclude-module", "test",
        "--exclude-module", "unittest",
        "--exclude-module", "pdb",
        "--exclude-module", "doctest",
        "main.py",
    ]
    
    ok, out, err = run_cmd(cmd)
    if ok:
        exe_path = Path("dist") / "opus.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"  ✓ Built: {exe_path} ({size_mb:.1f} MB)")
            return True
    
    print(f"  ERROR: Build failed: {err}")
    return False


def create_nsis_installer():
    """Create NSIS installer."""
    print("\n[INSTALLER] Creating NSIS installer...")
    
    # Check NSIS
    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    ]
    makensis = None
    for path in nsis_paths:
        if Path(path).exists():
            makensis = path
            break
    
    if not makensis:
        print("  NSIS not found, skipping installer creation")
        print("  Install NSIS from https://nsis.sourceforge.io/ to create installer")
        return False
    
    # Read version
    version = "1.0.0"
    try:
        import tomllib
        with open(USER_CONFIG_DIR / "config.toml", "rb") as f:
            cfg = tomllib.load(f)
            version = cfg.get("version", "1.0.0")
    except:
        pass
    
    exe_path = Path("dist/opus.exe")
    if not exe_path.exists():
        print("  opus.exe not found, run --build first")
        return False
    
    nsi_script = f'''!include "MUI2.nsh"

Name "OPUS Agent"
OutFile "OPUS-Agent-{version}-Setup.exe"
InstallDir "$PROGRAMFILES\\OPUS Agent"
InstallDirRegKey HKLM "Software\\OPUS Agent" ""
RequestExecutionLevel admin

!define MUI_ABORTWARNING
!define MUI_ICON "opus.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "PortugueseBR"

Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    File "dist\\opus.exe"
    
    # Create config directory
    CreateDirectory "$LOCALAPPDATA\\opus\\config_v2"
    CreateDirectory "$LOCALAPPDATA\\opus\\config_v2\\skills"
    CreateDirectory "$LOCALAPPDATA\\opus\\config_v2\\mcp"
    CreateDirectory "$LOCALAPPDATA\\opus\\config_v2\\sessions"
    CreateDirectory "$LOCALAPPDATA\\opus\\config_v2\\cache"
    CreateDirectory "$LOCALAPPDATA\\opus\\config_v2\\logs"
    
    # Copy default config if not exists
    IfFileExists "$LOCALAPPDATA\\opus\\config_v2\\config.toml" 0 +2
    File /oname=$LOCALAPPDATA\\opus\\config_v2\\config.toml "config_templates\\config.toml"
    2:
    
    # Copy skills
    File /r "skills\\*"
    
    # Copy MCP config
    File /oname=$LOCALAPPDATA\\opus\\config_v2\\mcp\\servers.toml "config_templates\\servers.toml"
    
    # Create uninstaller
    WriteUninstaller "$INSTDIR\\Uninstall.exe"
    
    # Registry
    WriteRegStr HKLM "Software\\OPUS Agent" "" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OPUS Agent" "DisplayName" "OPUS Agent"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OPUS Agent" "UninstallString" "$INSTDIR\\Uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OPUS Agent" "DisplayVersion" "{version}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OPUS Agent" "Publisher" "OPUS Agent"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OPUS Agent" "URLInfoAbout" "https://github.com/opus-agent/opus-agent"
    
    # Start menu
    CreateDirectory "$SMPROGRAMS\\OPUS Agent"
    CreateShortcut "$SMPROGRAMS\\OPUS Agent\\OPUS Agent.lnk" "$INSTDIR\\opus.exe"
    CreateShortcut "$SMPROGRAMS\\OPUS Agent\\Uninstall.lnk" "$INSTDIR\\Uninstall.exe"
    
    # Desktop shortcut
    CreateShortcut "$DESKTOP\\OPUS Agent.lnk" "$INSTDIR\\opus.exe"
    
    # Add to PATH (optional)
    ; ReadEnvStr $PATH "HKLM" "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment" "PATH"
    ; StrCmp $PATH "" 0 +3
    ; System::Call 'kernel32::SetEnvironmentVariable(t "PATH", t "$PATH;$INSTDIR")'
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\opus.exe"
    Delete "$INSTDIR\\Uninstall.exe"
    RMDir "$INSTDIR"
    
    Delete "$SMPROGRAMS\\OPUS Agent\\OPUS Agent.lnk"
    Delete "$SMPROGRAMS\\OPUS Agent\\Uninstall.lnk"
    RMDir "$SMPROGRAMS\\OPUS Agent"
    
    Delete "$DESKTOP\\OPUS Agent.lnk"
    
    DeleteRegKey HKLM "Software\\OPUS Agent"
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OPUS Agent"
SectionEnd

Function .onInit
    ; Check for admin rights
    UserInfo::GetAccountType
    Pop $0
    StrCmp $0 "Admin" 0 +2
    MessageBox MB_ICONEXCLAMATION "Este instalador requer permissoes de administrador.\\nPor favor, execute como administrador."
    Abort
FunctionEnd
'''
    
    # Create templates directory
    templates_dir = Path("config_templates")
    templates_dir.mkdir(exist_ok=True)
    
    config_toml = USER_CONFIG_DIR / "config.toml"
    if config_toml.exists():
        shutil.copy2(config_toml, templates_dir / "config.toml")
    
    mcp_toml = USER_CONFIG_DIR / "mcp" / "servers.toml"
    if mcp_toml.exists():
        shutil.copy2(mcp_toml, templates_dir / "servers.toml")
    
    # Copy skills to local skills folder for installer
    local_skills = Path("skills")
    if local_skills.exists():
        shutil.rmtree(local_skills)
    shutil.copytree(USER_SKILLS_DIR, local_skills)
    
    # Create LICENSE.txt
    if not Path("LICENSE.txt").exists():
        Path("LICENSE.txt").write_text("MIT License\n\nCopyright (c) 2024 OPUS Agent\n", encoding="utf-8")
    
    # Write NSI script
    nsi_file = Path("opus.nsi")
    nsi_file.write_text(nsi_script, encoding="utf-8")
    
    ok, out, err = run_cmd([makensis, str(nsi_file)])
    if ok:
        installer = Path(f"OPUS-Agent-{version}-Setup.exe")
        if installer.exists():
            size_mb = installer.stat().st_size / (1024 * 1024)
            print(f"  ✓ Created installer: {installer} ({size_mb:.1f} MB)")
            return True
    
    print(f"  ERROR: NSIS build failed: {err}")
    return False


def install_global() -> bool:
    """Install opus.exe globally (to %LOCALAPPDATA%\\opus\\bin) and add to PATH."""
    print("\n[GLOBAL] Installing opus globally...")
    
    exe_path = Path("dist/opus.exe")
    if not exe_path.exists():
        print("  opus.exe not found, run --build first")
        return False
    
    # Create global bin directory
    GLOBAL_BIN_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy executable
    target_exe = GLOBAL_BIN_DIR / "opus.exe"
    shutil.copy2(exe_path, target_exe)
    print(f"  ✓ Copied to {target_exe}")
    
    # Copy config_v2 to global config dir
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy default config if not exists
    global_config = GLOBAL_CONFIG_DIR / "config.toml"
    if not global_config.exists():
        config_toml = USER_CONFIG_DIR / "config.toml"
        if config_toml.exists():
            shutil.copy2(config_toml, global_config)
            print(f"  ✓ Copied config to {global_config}")
    
    # Copy MCP servers config if not exists
    global_mcp = GLOBAL_CONFIG_DIR / "mcp" / "servers.toml"
    if not global_mcp.exists():
        global_mcp.parent.mkdir(parents=True, exist_ok=True)
        mcp_toml = USER_CONFIG_DIR / "mcp" / "servers.toml"
        if mcp_toml.exists():
            shutil.copy2(mcp_toml, global_mcp)
            print(f"  ✓ Copied MCP config to {global_mcp}")
    
    # Copy skills
    global_skills = GLOBAL_CONFIG_DIR / "skills"
    if not global_skills.exists() or not any(global_skills.iterdir()):
        if global_skills.exists():
            shutil.rmtree(global_skills)
        shutil.copytree(USER_SKILLS_DIR, global_skills)
        print(f"  ✓ Copied skills to {global_skills}")
    
    # Add to user PATH
    add_to_user_path(str(GLOBAL_BIN_DIR))
    
    # Create opus.bat wrapper for cmd compatibility
    bat_path = GLOBAL_BIN_DIR / "opus.bat"
    bat_content = f'@echo off\n"{target_exe}" %*\n'
    bat_path.write_text(bat_content, encoding="utf-8")
    print(f"  ✓ Created {bat_path}")
    
    print(f"\n  ✓ Global install complete!")
    print(f"  Run 'opus' from any terminal (restart terminal to pick up PATH)")
    return True


def add_to_user_path(path: str) -> bool:
    """Add directory to user PATH environment variable."""
    try:
        # Get current user PATH
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            current_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current_path = ""
        
        # Check if already in PATH
        paths = [p.strip() for p in current_path.split(";") if p.strip()]
        if path in paths:
            print(f"  Already in PATH: {path}")
            winreg.CloseKey(key)
            return True
        
        # Add to PATH
        new_path = current_path + (";" if current_path else "") + path
        winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        
        # Notify system of environment change
        import ctypes
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, None
        )
        
        print(f"  ✓ Added to user PATH: {path}")
        return True
    except Exception as e:
        print(f"  WARNING: Could not add to PATH: {e}")
        return False


def create_uninstall_global() -> bool:
    """Create global uninstaller."""
    print("\n[GLOBAL] Creating uninstaller...")
    
    # Create uninstall script
    uninstall_script = GLOBAL_BIN_DIR / "uninstall_opus.bat"
    bin_dir = str(GLOBAL_BIN_DIR).replace("\\", "\\\\")
    config_dir = str(GLOBAL_CONFIG_DIR).replace("\\", "\\\\")
    content = f'''@echo off
echo Removendo OPUS Agent...
del /q "{bin_dir}\\\\opus.exe" 2>nul
del /q "{bin_dir}\\\\opus.bat" 2>nul
del /q "{bin_dir}\\\\uninstall_opus.bat" 2>nul
rmdir /s /q "{config_dir}" 2>nul

echo Removendo do PATH (requer reinicio do terminal)...
echo.
echo Para remover do PATH permanentemente, use:
echo   setx PATH "%%PATH:{bin_dir};=%%"
echo   setx PATH "%%PATH:{bin_dir}=%%"
echo.
pause
'''
    uninstall_script.write_text(content, encoding="utf-8")
    print(f"  ✓ Created {uninstall_script}")
    return True


def main():
    parser = argparse.ArgumentParser(description="OPUS Agent Installer")
    parser.add_argument("--dev", action="store_true", help="Development setup (deps + config + skills)")
    parser.add_argument("--build", action="store_true", help="Build PyInstaller executable")
    parser.add_argument("--installer", action="store_true", help="Create NSIS installer")
    parser.add_argument("--global-install", action="store_true", help="Install globally to %%LOCALAPPDATA%%\\opus\\bin and add to PATH", dest="global_install")
    parser.add_argument("--full", action="store_true", help="Full install: dev + build + installer + global")
    parser.add_argument("--verify", action="store_true", help="Verify installation only")
    args = parser.parse_args()
    
    if not any([args.dev, args.build, args.installer, args.global_install, args.full, args.verify]):
        args.full = True  # Default to full
    
    print("=" * 60)
    print("  OPUS Agent - Comprehensive Installer")
    print("=" * 60)
    
    success = True
    
    if args.verify:
        success = verify_installation()
    
    if args.dev or args.full:
        success = install_python_deps() and success
        success = install_playwright_browsers() and success
        success = setup_config_directories() and success
        success = copy_skills() and success
        success = create_default_config() and success
        success = create_mcp_servers_config() and success
        success = verify_installation() and success
    
    if args.build or args.full:
        success = build_executable() and success
    
    if args.global_install or args.full:
        success = install_global() and success
        success = create_uninstall_global() and success
    
    if args.installer or args.full:
        success = create_nsis_installer() and success
    
    print("\n" + "=" * 60)
    if success:
        print("  ✓ ALL OPERATIONS COMPLETED SUCCESSFULLY")
    else:
        print("  ✗ SOME OPERATIONS FAILED - Check output above")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())