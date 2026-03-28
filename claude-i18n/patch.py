"""
Claude Code i18n Patch — 繁體中文化工具
使用對照表逐一替換字串，不依賴程式碼結構，官方更新後只需更新對照表。

Usage:
  python patch.py                    # 自動 patch
  python patch.py --dry-run          # 預覽不修改
  python patch.py --restore          # 還原備份
  python patch.py --scan             # 掃描未翻譯的指令
  python patch.py --list             # 列出對照表
"""

import json
import os
import sys
import shutil
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TRANSLATIONS_FILE = SCRIPT_DIR / "translations.json"


def find_cli_js():
    """Find Claude Code's cli.js file."""
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


def patch(dry_run=False):
    """Apply translations to cli.js using simple string replacement."""
    cli_js = find_cli_js()
    if not cli_js:
        print("ERROR: 找不到 Claude Code 的 cli.js")
        print("請確認已用 npm install -g @anthropic-ai/claude-code 安裝")
        sys.exit(1)

    version = get_version(cli_js)
    print(f"Claude Code v{version}")
    print(f"cli.js: {cli_js}")

    backup_path = cli_js.with_suffix(".js.bak")
    trans = load_translations()

    with open(cli_js, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    changes = 0

    # Apply name translations
    for en, zh in trans.get("names", {}).items():
        if en in content and zh not in content:
            content = content.replace(en, zh, 1)
            cmd = en.split('"')[1]
            zh_name = zh.split('"')[1]
            print(f"  名稱: /{cmd} → /{zh_name}")
            changes += 1

    # Apply description translations
    for en, zh in trans.get("descriptions", {}).items():
        if en in content:
            content = content.replace(en, zh)
            print(f"  說明: {en[:30]}... → {zh[:30]}...")
            changes += 1

    # Apply alias injections
    for en, zh in trans.get("aliases", {}).items():
        if en in content and zh not in content:
            content = content.replace(en, zh, 1)
            changes += 1

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

    print(f"Patch 完成!")


def restore():
    """Restore from backup."""
    cli_js = find_cli_js()
    if not cli_js:
        print("ERROR: 找不到 cli.js")
        sys.exit(1)

    backup_path = cli_js.with_suffix(".js.bak")
    if backup_path.exists():
        shutil.copy2(backup_path, cli_js)
        print(f"已還原: {backup_path}")
    else:
        print("ERROR: 找不到備份")
        sys.exit(1)


def scan():
    """Scan for untranslated commands."""
    cli_js = find_cli_js()
    if not cli_js:
        print("ERROR: 找不到 cli.js")
        sys.exit(1)

    import re
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
            if not has_zh_name: status.append("名稱")
            if not has_zh_desc: status.append("說明")
            print(f"  /{name:<30} [{','.join(status)}英文] {desc}")

    print(f"\n中文: {zh_count}, 英文: {en_count}, 覆蓋率: {zh_count}/{zh_count+en_count} ({zh_count*100//(zh_count+en_count) if zh_count+en_count else 0}%)")


def list_translations():
    """List all translations."""
    trans = load_translations()
    names = trans.get("names", {})
    print(f"=== 對照表 ({len(names)} 個指令) ===")
    print(f"{'英文':<30} {'中文'}")
    print("-" * 60)
    for en, zh in sorted(names.items()):
        en_name = en.split('"')[1]
        zh_name = zh.split('"')[1]
        print(f"/{en_name:<29} /{zh_name}")


def main():
    args = sys.argv[1:]

    if "--restore" in args:
        restore()
    elif "--scan" in args:
        scan()
    elif "--list" in args:
        list_translations()
    elif "--dry-run" in args:
        patch(dry_run=True)
    else:
        patch()


if __name__ == "__main__":
    main()
