"""claude-wrapper.py — Claude Code 中文化啟動器。
檢查 claude.exe 是否需要重新 patch，自動維護中文化。
用法：直接取代 claude 指令使用。
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = Path.home() / ".claude-i18n-state.json"


def get_file_hash(path):
    """計算檔案 SHA256（只讀前 1MB + 後 1MB 加速）。"""
    h = hashlib.sha256()
    size = path.stat().st_size
    with open(path, 'rb') as f:
        h.update(f.read(1024 * 1024))  # first 1MB
        if size > 2 * 1024 * 1024:
            f.seek(-1024 * 1024, 2)
            h.update(f.read())  # last 1MB
    return h.hexdigest()


def find_claude_exe():
    """找到真正的 claude.exe（winget 或 npm）。"""
    # winget
    winget_base = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    if winget_base.exists():
        import glob as g
        matches = g.glob(str(winget_base / "Anthropic.ClaudeCode_*" / "claude.exe"))
        if matches:
            return Path(sorted(matches, key=os.path.getmtime, reverse=True)[0]), "winget"

    # npm cli.js
    try:
        result = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=10)
        cli_js = Path(result.stdout.strip()) / "@anthropic-ai" / "claude-code" / "cli.js"
        if cli_js.exists():
            return cli_js, "npm"
    except Exception:
        pass

    return None, None


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def needs_patch(exe_path, mode):
    """檢查是否需要重新 patch。"""
    state = load_state()
    current_hash = get_file_hash(exe_path)
    return current_hash != state.get("last_patched_hash")


def run_patch(mode):
    """執行 patch。"""
    patch_script = SCRIPT_DIR / "patch.py"
    flag = "--winget" if mode == "winget" else "--npm"
    result = subprocess.run(
        [sys.executable, str(patch_script), flag],
        capture_output=True, text=True, timeout=120
    )
    return result.returncode == 0, result.stdout


def main():
    exe_path, mode = find_claude_exe()
    if not exe_path:
        print("ERROR: 找不到 Claude Code")
        sys.exit(1)

    # Check if patch needed
    if needs_patch(exe_path, mode):
        print("[claude-i18n] 偵測到更新，自動重新中文化...", file=sys.stderr)
        ok, output = run_patch(mode)
        if ok:
            # Update state
            state = load_state()
            state["last_patched_hash"] = get_file_hash(exe_path)
            state["mode"] = mode
            state["exe_path"] = str(exe_path)
            save_state(state)
            print("[claude-i18n] 中文化完成!", file=sys.stderr)
        else:
            print("[claude-i18n] 中文化失敗，使用英文版", file=sys.stderr)

    # Launch real claude
    if mode == "winget":
        os.execv(str(exe_path), [str(exe_path)] + sys.argv[1:])
    else:
        # npm mode: run node with cli.js
        os.execv(sys.executable, [sys.executable, str(exe_path)] + sys.argv[1:])


if __name__ == "__main__":
    main()
