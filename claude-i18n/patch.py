"""
Claude Code i18n Patch‍‌​‍​‌ — 繁體中文化工具
使用對照表逐一替換字串，不依賴程式碼結構，官方更新後只需更新對照表。
支援 npm 安裝版（cli.js）及 winget 安裝版（claude.exe binary）。

Usage:
  python patch.py                    # 自動偵測（npm 優先，找不到就用 winget）
  python patch.py --winget           # 強制使用 winget 版
  python patch.py --npm              # 強制使用 npm 版
  python patch.py --dry-run          # 預覽不修改
  python patch.py --dry-run --winget # 預覽 winget 版
  python patch.py --restore          # 還原備份
  python patch.py --restore --winget # 還原 winget 備份
  python patch.py --scan             # 掃描未翻譯的指令
  python patch.py --list             # 列出對照表
"""

import glob as globmod
import json
import os
import re
import sys
import shutil
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TRANSLATIONS_FILE = SCRIPT_DIR / "translations.json"

# 187 English thinking verbs in display order (must match Claude Code source)
ENGLISH_SPINNERS = [
    "Accomplishing", "Actioning", "Actualizing", "Architecting", "Baking",
    "Beaming", "Beboppin'", "Befuddling", "Billowing", "Blanching",
    "Bloviating", "Boogieing", "Boondoggling", "Booping", "Bootstrapping",
    "Brewing", "Bunning", "Burrowing", "Calculating", "Canoodling",
    "Caramelizing", "Cascading", "Catapulting", "Cerebrating", "Channeling",
    "Channelling", "Choreographing", "Churning", "Clauding", "Coalescing",
    "Cogitating", "Combobulating", "Composing", "Computing", "Concocting",
    "Considering", "Contemplating", "Cooking", "Crafting", "Creating",
    "Crunching", "Crystallizing", "Cultivating", "Deciphering", "Deliberating",
    "Determining", "Dilly-dallying", "Discombobulating", "Doing", "Doodling",
    "Drizzling", "Ebbing", "Effecting", "Elucidating", "Embellishing",
    "Enchanting", "Envisioning", "Evaporating", "Fermenting", "Fiddle-faddling",
    "Finagling", "Flambéing", "Flibbertigibbeting", "Flowing", "Flummoxing",
    "Fluttering", "Forging", "Forming", "Frolicking", "Frosting",
    "Gallivanting", "Galloping", "Garnishing", "Generating", "Gesticulating",
    "Germinating", "Gitifying", "Grooving", "Gusting", "Harmonizing",
    "Hashing", "Hatching", "Herding", "Honking", "Hullaballooing",
    "Hyperspacing", "Ideating", "Imagining", "Improvising", "Incubating",
    "Inferring", "Infusing", "Ionizing", "Jitterbugging", "Julienning",
    "Kneading", "Leavening", "Levitating", "Lollygagging", "Manifesting",
    "Marinating", "Meandering", "Metamorphosing", "Misting", "Moonwalking",
    "Moseying", "Mulling", "Mustering", "Musing", "Nebulizing",
    "Nesting", "Newspapering", "Noodling", "Nucleating", "Orbiting",
    "Orchestrating", "Osmosing", "Perambulating", "Percolating", "Perusing",
    "Philosophising", "Photosynthesizing", "Pollinating", "Pondering", "Pontificating",
    "Pouncing", "Precipitating", "Prestidigitating", "Processing", "Proofing",
    "Propagating", "Puttering", "Puzzling", "Quantumizing", "Razzle-dazzling",
    "Razzmatazzing", "Recombobulating", "Reticulating", "Roosting", "Ruminating",
    "Sautéing", "Scampering", "Schlepping", "Scurrying", "Seasoning",
    "Shenaniganing", "Shimmying", "Simmering", "Skedaddling", "Sketching",
    "Slithering", "Smooshing", "Sock-hopping", "Spelunking", "Spinning",
    "Sprouting", "Stewing", "Sublimating", "Swirling", "Swooping",
    "Symbioting", "Synthesizing", "Tempering", "Thinking", "Thundering",
    "Tinkering", "Tomfoolering", "Topsy-turvying", "Transfiguring", "Transmuting",
    "Twisting", "Undulating", "Unfurling", "Unravelling", "Vibing",
    "Waddling", "Wandering", "Warping", "Whatchamacalliting", "Whirlpooling",
    "Whirring", "Whisking", "Wibbling", "Working", "Wrangling",
    "Zesting", "Zigzagging",
]


def find_cli_js():
    """Find Claude Code's cli.js file (npm version)."""
    try:
        result = subprocess.run(
            ["npm", "root", "-g"],
            capture_output=True, text=True, timeout=10
        )
        npm_root = result.stdout.strip()
        cli_js = Path(npm_root) / "@anthropic-ai" / "claude-code" / "cli.js"
        if cli_js.exists():
            return cli_js
    except Exception:
        pass

    candidates = [
        Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js",
        Path.home() / ".npm-global" / "lib" / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js",
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def find_winget_exe():
    """Find Claude Code's claude.exe installed via winget."""
    local_app = Path.home() / "AppData" / "Local"
    # WinGet packages dir — the folder name varies by source hash
    winget_base = local_app / "Microsoft" / "WinGet" / "Packages"
    if winget_base.exists():
        # Match any Anthropic.ClaudeCode_* directory
        pattern = str(winget_base / "Anthropic.ClaudeCode_*" / "claude.exe")
        matches = globmod.glob(pattern)
        if matches:
            # Pick the newest if multiple versions exist
            matches.sort(key=os.path.getmtime, reverse=True)
            return Path(matches[0])

    # Fallback: check if claude.exe is on PATH and is the winget version (>100MB)
    try:
        result = subprocess.run(
            ["where", "claude.exe"], capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().splitlines():
            p = Path(line.strip())
            if p.exists() and p.stat().st_size > 100_000_000:  # >100MB = bundled binary
                return p
    except Exception:
        pass
    return None


def get_version(cli_js_path):
    """Get Claude Code version from package.json."""
    pkg = cli_js_path.parent / "package.json"
    if pkg.exists():
        with open(pkg, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "unknown")
    return "unknown"


def load_translations():
    """Load translation table from JSON."""
    with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_translations(content, trans, verbose=True):
    """Apply all translation categories to content. Returns (new_content, change_count)."""
    changes = 0

    # 1. Command name translations
    for en, zh in trans.get("names", {}).items():
        if en in content and zh not in content:
            content = content.replace(en, zh, 1)
            if verbose:
                cmd = en.split('"')[1]
                zh_name = zh.split('"')[1]
                print(f"  名稱: /{cmd} → /{zh_name}")
            changes += 1

    # 2. Description translations
    for en, zh in trans.get("descriptions", {}).items():
        if en in content:
            content = content.replace(en, zh)
            if verbose:
                print(f"  說明: {en[:30]}... → {zh[:30]}...")
            changes += 1

    # 3. Alias injections
    for en, zh in trans.get("aliases", {}).items():
        if en in content and zh not in content:
            content = content.replace(en, zh, 1)
            changes += 1

    # 4. Thinking spinner verbs (replace entire array)
    zh_spinners = trans.get("ui_spinners", [])
    if zh_spinners and len(zh_spinners) == len(ENGLISH_SPINNERS):
        en_arr = "[" + ",".join(f'"{v}"' for v in ENGLISH_SPINNERS) + "]"
        zh_arr = "[" + ",".join(f'"{v}"' for v in zh_spinners) + "]"
        if en_arr in content:
            content = content.replace(en_arr, zh_arr, 1)
            if verbose:
                print(f"  思考動畫: {len(zh_spinners)} 個動詞已翻譯")
            changes += 1

    # 5. Completion verbs
    for en, zh in trans.get("ui_completion", {}).items():
        if en in content:
            content = content.replace(en, zh)
            if verbose:
                print(f"  完成提示: {en} → {zh}")
            changes += 1

    # 6. Status/template strings
    for en, zh in trans.get("ui_status", {}).items():
        if en in content:
            content = content.replace(en, zh)
            if verbose:
                print(f"  狀態: {repr(en)} → {repr(zh)}")
            changes += 1

    # 7. Tip messages
    for en, zh in trans.get("ui_tips", {}).items():
        if en in content:
            content = content.replace(en, zh)
            if verbose:
                print(f"  提示: {en[:30]}... → {zh[:30]}...")
            changes += 1

    # 8. Misc UI strings
    for en, zh in trans.get("ui_misc", {}).items():
        if en in content:
            content = content.replace(en, zh)
            if verbose:
                print(f"  介面: {en[:30]} → {zh[:30]}")
            changes += 1

    return content, changes


def _binary_replace(data, old_str, new_str, verbose=True, label=""):
    """Replace old_str with new_str in binary data, padding with spaces if new is shorter.
    Returns (new_data, replaced) where replaced is True if substitution happened."""
    old_bytes = old_str.encode("utf-8")
    new_bytes = new_str.encode("utf-8")
    old_len = len(old_bytes)
    new_len = len(new_bytes)

    if new_len > old_len:
        if verbose:
            print(f"  [跳過] {label}: 中文 {new_len}B > 英文 {old_len}B (超出 {new_len - old_len}B)")
        return data, False

    if old_bytes not in data:
        return data, False

    # Pad with spaces to match original byte length
    padded = new_bytes + b" " * (old_len - new_len)
    count = data.count(old_bytes)
    data = data.replace(old_bytes, padded)
    if verbose:
        saved = old_len - new_len
        suffix = f" ×{count}" if count > 1 else ""
        print(f"  {label}: {old_len}B → {new_len}B (填充 {saved}B){suffix}")
    return data, True


def apply_binary_translations(exe_path, trans, dry_run=False):
    """Apply translations to winget claude.exe binary via byte-level replacement.
    Returns change count."""
    print(f"讀取 binary: {exe_path} ({exe_path.stat().st_size / 1024 / 1024:.0f} MB)")

    with open(exe_path, "rb") as f:
        data = f.read()

    original_size = len(data)
    changes = 0
    skipped = 0

    # 1. Command name translations (binary mode: pure Chinese, no parenthetical)
    binary_names = trans.get("binary_names", {})
    if not binary_names:
        binary_names = trans.get("names", {})  # fallback
    print(f"\n--- 指令名稱 ({len(binary_names)} 個) ---")
    for en, zh in binary_names.items():
        data, ok = _binary_replace(data, en, zh, verbose=True,
                                   label=en.split('"')[1] if '"' in en else en[:20])
        if ok:
            changes += 1
        elif en.encode("utf-8") in data:
            skipped += 1

    # 2. Description translations
    print("\n--- 指令說明 ---")
    for en, zh in trans.get("descriptions", {}).items():
        data, ok = _binary_replace(data, en, zh, verbose=True,
                                   label=en[:30].strip('"'))
        if ok:
            changes += 1
        elif en.encode("utf-8") in data:
            skipped += 1

    # 3. Alias injections
    print("\n--- 別名注入 ---")
    for en, zh in trans.get("aliases", {}).items():
        zh_bytes = zh.encode("utf-8")
        if zh_bytes in data:
            print(f"  [已存在] {en[:30]}")
            continue
        data, ok = _binary_replace(data, en, zh, verbose=True,
                                   label=en[:30])
        if ok:
            changes += 1
        elif en.encode("utf-8") in data:
            skipped += 1

    # 4. Thinking spinner verbs — individually replace each verb
    zh_spinners = trans.get("ui_spinners", [])
    if zh_spinners and len(zh_spinners) == len(ENGLISH_SPINNERS):
        print(f"\n--- 思考動畫 ({len(ENGLISH_SPINNERS)} 個動詞) ---")
        spinner_ok = 0
        spinner_skip = 0
        for i, en_verb in enumerate(ENGLISH_SPINNERS):
            zh_verb = zh_spinners[i]
            # In the binary, spinner verbs appear as "Verb" in a JSON array
            en_str = f'"{en_verb}"'
            zh_str = f'"{zh_verb}"'
            data, ok = _binary_replace(data, en_str, zh_str, verbose=False)
            if ok:
                spinner_ok += 1
            else:
                en_b = en_str.encode("utf-8")
                zh_b = zh_str.encode("utf-8")
                if en_b in data and len(zh_b) > len(en_b):
                    spinner_skip += 1
        print(f"  替換: {spinner_ok}, 跳過(太長): {spinner_skip}, "
              f"未找到: {len(ENGLISH_SPINNERS) - spinner_ok - spinner_skip}")
        if spinner_ok:
            changes += 1

    # 5. Completion verbs
    print("\n--- 完成提示 ---")
    for en, zh in trans.get("ui_completion", {}).items():
        data, ok = _binary_replace(data, en, zh, verbose=True,
                                   label=en.strip('"'))
        if ok:
            changes += 1
        elif en.encode("utf-8") in data:
            skipped += 1

    # 6. Status/template strings
    print("\n--- 狀態字串 ---")
    for en, zh in trans.get("ui_status", {}).items():
        data, ok = _binary_replace(data, en, zh, verbose=True,
                                   label=repr(en)[:30])
        if ok:
            changes += 1
        elif en.encode("utf-8") in data:
            skipped += 1

    # 7. Tip messages
    print("\n--- 操作提示 ---")
    for en, zh in trans.get("ui_tips", {}).items():
        data, ok = _binary_replace(data, en, zh, verbose=True,
                                   label=en[:30])
        if ok:
            changes += 1
        elif en.encode("utf-8") in data:
            skipped += 1

    # 8. Misc UI strings
    print("\n--- 介面字串 ---")
    for en, zh in trans.get("ui_misc", {}).items():
        data, ok = _binary_replace(data, en, zh, verbose=True,
                                   label=en[:30])
        if ok:
            changes += 1
        elif en.encode("utf-8") in data:
            skipped += 1

    # 9. Constant pool: template literal fragments
    # Bundler splits template literals into length-prefixed constant pool entries.
    # Note: " effort" kept in English — constant pool can't reorder to "精力Lv:X"
    print("\n--- Constant pool 模板片段 ---")
    pool_replacements = []
    if not pool_replacements:
        print("  (無替換項目)")

    # Sanity check: size must not change
    assert len(data) == original_size, \
        f"BUG: binary size changed! {original_size} → {len(data)}"

    print(f"\n共 {changes} 類替換, {skipped} 處因長度超出而跳過")

    if changes == 0:
        print("已經是最新狀態或無可替換項目")
        return changes

    if dry_run:
        print("(--dry-run 模式，未修改檔案)")
        return changes

    # Backup
    backup_path = exe_path.with_suffix(".exe.bak")
    if not backup_path.exists():
        print(f"備份: {backup_path}")
        shutil.copy2(exe_path, backup_path)
    else:
        print(f"備份已存在: {backup_path}")

    with open(exe_path, "wb") as f:
        f.write(data)

    print(f"Binary Patch 完成! ({exe_path})")
    return changes


def patch_winget(dry_run=False):
    """Apply translations to winget claude.exe binary."""
    exe = find_winget_exe()
    if not exe:
        print("ERROR: 找不到 winget 版的 claude.exe")
        print("預期路徑: %LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\Anthropic.ClaudeCode_*\\claude.exe")
        sys.exit(1)

    print(f"claude.exe: {exe}")
    trans = load_translations()
    apply_binary_translations(exe, trans, dry_run=dry_run)


def restore_winget():
    """Restore winget claude.exe from backup."""
    exe = find_winget_exe()
    if not exe:
        print("ERROR: 找不到 winget 版的 claude.exe")
        sys.exit(1)
    backup_path = exe.with_suffix(".exe.bak")
    if backup_path.exists():
        shutil.copy2(backup_path, exe)
        print(f"已還原: {exe}")
    else:
        print("ERROR: 找不到備份 (.exe.bak)")
        sys.exit(1)


def patch(dry_run=False):
    """Apply translations to cli.js using simple string replacement."""
    cli_js = find_cli_js()
    if not cli_js:
        print("ERROR: 找不到 Claude Code 的 cli.js (npm 版)")
        print("請確認已用 npm install -g @anthropic-ai/claude-code 安裝")
        print("提示：如果是 winget 安裝，請使用 --winget 參數")
        sys.exit(1)

    version = get_version(cli_js)
    print(f"Claude Code v{version}")
    print(f"cli.js: {cli_js}")

    backup_path = cli_js.with_suffix(".js.bak")
    trans = load_translations()

    with open(cli_js, "r", encoding="utf-8") as f:
        content = f.read()

    content, changes = apply_translations(content, trans)

    if changes == 0:
        print("\n已經是最新狀態，無需 patch")
        return

    print(f"\n共 {changes} 處替換")

    if dry_run:
        print("(--dry-run 模式，未修改檔案)")
        return

    # Backup
    if not backup_path.exists():
        shutil.copy2(cli_js, backup_path)
        print(f"備份: {backup_path}")

    with open(cli_js, "w", encoding="utf-8") as f:
        f.write(content)

    print("Patch 完成!")


def restore():
    """Restore from backup."""
    cli_js = find_cli_js()
    if not cli_js:
        print("ERROR: 找不到 cli.js")
        sys.exit(1)
    backup_path = cli_js.with_suffix(".js.bak")

    if backup_path.exists():
        shutil.copy2(backup_path, cli_js)
        print(f"已還原: {cli_js}")
    else:
        print("ERROR: 找不到備份")
        sys.exit(1)


def scan():
    """Scan for untranslated commands in cli.js."""
    cli_js = find_cli_js()
    if not cli_js:
        print("ERROR: 找不到 cli.js")
        sys.exit(1)

    with open(cli_js, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r'type:\s*["\'](?:local|prompt|local-jsx)["\']\s*,\s*name:\s*["\']([\w\(\)\-\u4e00-\u9fff]+)["\']\s*,\s*description:\s*["\'](.*?)["\']'

    zh_count = 0
    en_count = 0
    print("=== 未翻譯的指令 ===")
    for m in re.finditer(pattern, content):
        name = m.group(1)
        desc = m.group(2)[:60]
        has_zh_name = any('\u4e00' <= c <= '\u9fff' for c in name)
        has_zh_desc = any('\u4e00' <= c <= '\u9fff' for c in desc)
        if has_zh_name and has_zh_desc:
            zh_count += 1
        else:
            en_count += 1
            status = []
            if not has_zh_name:
                status.append("名稱")
            if not has_zh_desc:
                status.append("說明")
            print(f"  /{name:<30} [{','.join(status)}英文] {desc}")

    total = zh_count + en_count
    pct = zh_count * 100 // total if total else 0
    print(f"\n中文: {zh_count}, 英文: {en_count}, 覆蓋率: {zh_count}/{total} ({pct}%)")


def list_translations():
    """List all translations."""
    trans = load_translations()
    names = trans.get("names", {})
    spinners = trans.get("ui_spinners", [])
    completion = trans.get("ui_completion", {})
    tips = trans.get("ui_tips", {})

    print(f"=== 指令對照表 ({len(names)} 個) ===")
    print(f"{'英文':<30} {'中文'}")
    print("-" * 60)
    for en, zh in sorted(names.items()):
        en_name = en.split('"')[1]
        zh_name = zh.split('"')[1]
        print(f"/{en_name:<29} /{zh_name}")

    if spinners:
        print(f"\n=== 思考動畫 ({len(spinners)} 個) ===")
        for i, zh in enumerate(spinners):
            en = ENGLISH_SPINNERS[i] if i < len(ENGLISH_SPINNERS) else "?"
            print(f"  {en:<25} → {zh}")

    if completion:
        print(f"\n=== 完成提示 ({len(completion)} 個) ===")
        for en, zh in completion.items():
            print(f"  {en:<20} → {zh}")

    if tips:
        print(f"\n=== 操作提示 ({len(tips)} 個) ===")
        for en, zh in tips.items():
            print(f"  {en[:40]}... → {zh[:40]}...")


def auto_detect_mode():
    """Auto-detect: prefer npm, fall back to winget."""
    if find_cli_js():
        return "npm"
    if find_winget_exe():
        return "winget"
    return None


def main():
    args = sys.argv[1:]
    force_winget = "--winget" in args
    force_npm = "--npm" in args
    dry_run = "--dry-run" in args

    if "--restore" in args:
        if force_winget:
            restore_winget()
        else:
            restore()
    elif "--scan" in args:
        scan()
    elif "--list" in args:
        list_translations()
    else:
        # Determine target
        if force_winget:
            mode = "winget"
        elif force_npm:
            mode = "npm"
        else:
            mode = auto_detect_mode()

        if mode == "winget":
            print("[模式: winget binary]")
            patch_winget(dry_run=dry_run)
        elif mode == "npm":
            print("[模式: npm cli.js]")
            patch(dry_run=dry_run)
        else:
            print("ERROR: 找不到 Claude Code 安裝")
            print("  npm 版: npm install -g @anthropic-ai/claude-code")
            print("  winget 版: winget install Anthropic.ClaudeCode")
            sys.exit(1)


if __name__ == "__main__":
    main()
