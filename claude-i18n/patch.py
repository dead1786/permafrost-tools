"""
Claude Code i18n Patch — 繁體中文化工具
使用對照表逐一替換字串，不依賴程式碼結構，官方更新後只需更新對照表。
僅支援 npm 安裝版（cli.js）。

Usage:
  python patch.py                    # 自動 patch
  python patch.py --dry-run          # 預覽不修改
  python patch.py --restore          # 還原備份
  python patch.py --scan             # 掃描未翻譯的指令
  python patch.py --list             # 列出對照表
"""

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

    return content, changes


def patch(dry_run=False):
    """Apply translations to cli.js using simple string replacement."""
    cli_js = find_cli_js()
    if not cli_js:
        print("ERROR: 找不到 Claude Code 的 cli.js")
        print("請確認已用 npm install -g @anthropic-ai/claude-code 安裝")
        print("注意：僅支援 npm 版，不支援原生 .exe 版（winget）")
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
