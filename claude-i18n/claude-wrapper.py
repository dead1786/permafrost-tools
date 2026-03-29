"""claude-wrapper.py — Claude Code 中文化啟動器。
檢查 claude.exe 是否需要重新 patch，自動維護中文化。
啟動時自動檢查翻譯包新版本（每 24 小時一次，不強制更新）。
用法：直接取代 claude 指令使用。
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = Path.home() / ".claude-i18n-state.json"
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/dead1786/permafrost-tools/master/claude-i18n/VERSION"
UPDATE_CHECK_INTERVAL = 86400  # 24 小時


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


def check_for_updates():
    """檢查翻譯包是否有新版本（每 24h 一次，失敗靜默跳過）。"""
    try:
        state = load_state()
        last_check = state.get("last_update_check", 0)
        if time.time() - last_check < UPDATE_CHECK_INTERVAL:
            return

        # 讀本地版本
        local_ver_file = SCRIPT_DIR / "VERSION"
        if not local_ver_file.exists():
            return
        local_ver = local_ver_file.read_text(encoding="utf-8").strip()

        # 查遠端版本（3 秒超時）
        req = urllib.request.Request(REMOTE_VERSION_URL, headers={"User-Agent": "claude-i18n"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            remote_ver = resp.read().decode("utf-8").strip()

        # 記錄檢查時間（不管結果如何都更新，避免頻繁重試）
        state["last_update_check"] = time.time()
        save_state(state)

        if remote_ver and remote_ver != local_ver:
            print(f"[claude-i18n] 新版翻譯 v{remote_ver} 可用（目前 v{local_ver}）", file=sys.stderr)
            print(f"[claude-i18n] 更新指令: cd {SCRIPT_DIR} && git pull && python patch.py", file=sys.stderr)
    except Exception:
        # 網路失敗、超時、DNS 錯誤 — 全部靜默跳過
        pass


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

    # 非阻塞檢查翻譯包更新
    check_for_updates()

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
