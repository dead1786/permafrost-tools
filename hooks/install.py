#!/usr/bin/env python3
"""
install.py — One-click setup for the self-guard Stop hook

Copies self-guard.py (+ its config/schema) into ~/.claude/hooks/ and
registers it in ~/.claude/settings.json using the matcher-group schema
Claude Code actually expects for hook definitions:

    {"hooks": {"Stop": [{"hooks": [{"type": "command", ...}]}]}}

The README's previous manual instructions showed a flat entry
(`"Stop": [{"type": "command", ...}]`) missing the inner "hooks" array —
that shape does not match Claude Code's real settings.json schema. This
installer always emits the correct nested form, and — critically — it
APPENDS a new matcher-group entry instead of overwriting `hooks.Stop`,
so any Stop hooks you already have configured are left untouched.

Usage:
  python install.py              # Install (copy files + register hook)
  python install.py --status     # Check whether it's installed
  python install.py --uninstall  # Remove the registration (keeps copied files)
"""
import json
import os
import shutil
import sys

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
HOOKS_DEST_DIR = os.path.join(CLAUDE_DIR, "hooks")
SETTINGS_FILE = os.path.join(CLAUDE_DIR, "settings.json")

# (filename, overwrite_on_reinstall) — code always updates; user data/config
# is left alone if it already exists, same convention as frost-scheduler/install.py
FILES_TO_COPY = [
    ("self-guard.py", True),
    ("self-guard-config-schema.json", True),
    ("self-guard-config.json", False),
]

DEFAULT_TIMEOUT = 5


def dest_script_path():
    return os.path.join(HOOKS_DEST_DIR, "self-guard.py")


def build_command():
    script_path = dest_script_path().replace("\\", "/")
    return f'python "{script_path}"'


def read_settings():
    """Load settings.json, or {} if it doesn't exist yet.

    Aborts (rather than silently returning {}) if the file exists but is
    not valid JSON — proceeding would mean writing our hook back out as a
    brand-new settings.json, destroying every other setting the user has.
    """
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: {SETTINGS_FILE} exists but is not valid JSON ({e}).")
        print("Refusing to touch it — fix the JSON manually, then re-run install.py.")
        sys.exit(1)


def write_settings(settings):
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")


def is_self_guard_entry(entry):
    """True if a Stop matcher-group entry's hooks[] runs self-guard.py."""
    for h in entry.get("hooks", []) if isinstance(entry, dict) else []:
        if isinstance(h, dict) and h.get("type") == "command" and "self-guard.py" in h.get("command", ""):
            return True
    return False


def find_self_guard(settings):
    stop_hooks = settings.get("hooks", {}).get("Stop", [])
    for entry in stop_hooks:
        if is_self_guard_entry(entry):
            return entry
    return None


def copy_files():
    os.makedirs(HOOKS_DEST_DIR, exist_ok=True)
    for name, overwrite in FILES_TO_COPY:
        src = os.path.join(TOOL_DIR, name)
        dst = os.path.join(HOOKS_DEST_DIR, name)
        if os.path.exists(dst) and not overwrite:
            print(f"  Skipped (already exists, not overwriting your customization): {dst}")
            continue
        shutil.copy2(src, dst)
        print(f"  Installed: {dst}")


def install():
    print("Installing self-guard...")
    copy_files()

    settings = read_settings()
    settings.setdefault("hooks", {})
    settings["hooks"].setdefault("Stop", [])

    if find_self_guard(settings):
        print("  Already registered in settings.json — nothing to change.")
        return

    # Appended as its own matcher-group entry so any pre-existing Stop
    # hooks (yours or another tool's) are preserved, not replaced.
    settings["hooks"]["Stop"].append({
        "hooks": [
            {
                "type": "command",
                "command": build_command(),
                "timeout": DEFAULT_TIMEOUT,
            }
        ]
    })
    write_settings(settings)
    print(f"  Registered in: {SETTINGS_FILE}")
    print("\nDone. self-guard now runs on every Stop event.")
    print("Customize detection patterns in:", os.path.join(HOOKS_DEST_DIR, "self-guard-config.json"))


def uninstall():
    settings = read_settings()
    stop_hooks = settings.get("hooks", {}).get("Stop", [])
    remaining = [e for e in stop_hooks if not is_self_guard_entry(e)]

    if len(remaining) == len(stop_hooks):
        print("self-guard is not registered in settings.json — nothing to remove.")
        return

    if remaining:
        settings["hooks"]["Stop"] = remaining
    else:
        settings.get("hooks", {}).pop("Stop", None)
    if "hooks" in settings and not settings["hooks"]:
        settings.pop("hooks", None)

    write_settings(settings)
    print("Removed self-guard from settings.json.")
    print(f"(Copied files under {HOOKS_DEST_DIR} were left in place.)")


def status():
    settings = read_settings()
    entry = find_self_guard(settings)
    if entry:
        cmd = next(
            (h.get("command") for h in entry.get("hooks", []) if "self-guard.py" in h.get("command", "")),
            "?",
        )
        print(f"self-guard: REGISTERED\n  command: {cmd}")
    else:
        print("self-guard: NOT registered in settings.json")

    present = [name for name, _ in FILES_TO_COPY if os.path.exists(os.path.join(HOOKS_DEST_DIR, name))]
    missing = [name for name, _ in FILES_TO_COPY if name not in present]
    print(f"Files present in {HOOKS_DEST_DIR}: {present or 'none'}")
    if missing:
        print(f"Files missing: {missing}")


def main():
    if "--uninstall" in sys.argv:
        uninstall()
    elif "--status" in sys.argv:
        status()
    else:
        install()


if __name__ == "__main__":
    main()
