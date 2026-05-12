# Contributing to Permafrost Tools

Thanks for your interest in contributing! This project is a collection of independent tools — each one solves a specific problem for Claude Code users. Contributions that make these tools more reliable, more portable, or support more languages are especially welcome.

## Getting Started

1. Fork the repo
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/permafrost-tools.git`
3. Create a branch: `git checkout -b feat/my-feature`
4. Make your changes
5. Test your changes (see below)
6. Push and open a PR

## Project Structure

```
permafrost-tools/
  claude-whisper/     # npm package — dynamic runtime instructions (Node.js)
  claude-i18n/        # Claude Code localization patcher (Python)
  hooks/              # Claude Code hooks (Python)
    self-guard.py     # AI behavior detection
  tools/              # Standalone utilities (Python)
    memory-gc.py
    pitfall-tracker.py
    frost-scheduler/
    frost-collab/
```

Each tool is self-contained. You can work on one without touching the others.

## Good First Contributions

### Add a language to claude-i18n

The highest-impact contribution you can make:

1. Copy `claude-i18n/translations.json` to `claude-i18n/translations-XX.json` (e.g., `translations-ja.json` for Japanese)
2. Translate the values (keys stay the same)
3. Test with `python patch.py --dry-run`
4. Submit a PR

### Add detection patterns to self-guard

Edit `hooks/self-guard-config.json` to add new patterns for sycophancy, passive deferral, or other bad AI behaviors. Patterns are Python regex strings.

### Fix bugs or improve docs

Found something broken? A confusing README section? Missing an edge case? PRs welcome.

## Guidelines

- **Zero or minimal dependencies.** Python tools use stdlib only. Node.js uses built-ins only. Don't add `npm install` or `pip install` requirements.
- **Test on your machine.** These tools interact with Claude Code's file system — make sure they work before submitting.
- **Keep tools independent.** Each tool should work on its own without requiring other tools from this repo.
- **Cross-platform when possible.** Windows, macOS, and Linux. Use `os.path` / `pathlib`, not hardcoded paths.

## Testing

### claude-whisper

```bash
cd claude-whisper
node bin/cli.mjs help
node bin/cli.mjs init
node bin/cli.mjs add "test whisper"
node bin/cli.mjs ls
node bin/cli.mjs rm 1
```

### claude-i18n

```bash
cd claude-i18n
python patch.py --dry-run    # Preview without modifying
python patch.py --list       # Check translation table
```

### self-guard

```bash
echo '{"stop_hook_active": false, "last_assistant_message": "Want me to fix that for you?"}' | python hooks/self-guard.py
# Should output a block decision
```

### Python tools

```bash
python tools/memory-gc.py stats
python tools/pitfall-tracker.py list
```

## Commit Style

We use conventional commits:

```
feat(claude-whisper): add export command
fix(self-guard): handle empty transcript
docs(claude-i18n): update winget instructions
```

## Questions?

Open an issue. We're friendly.
