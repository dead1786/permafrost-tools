# Permafrost Tools v0.3.0 — Release Notes Draft

> Internal draft. Delete this file before publishing.

---

## GitHub Release Title

```
v0.3.0 — claude-i18n, self-guard overhaul, 7 tools
```

## GitHub Release Body

```markdown
## What's New in v0.3.0

### claude-i18n — Claude Code Command Localization (NEW)

Localize all 55+ Claude Code built-in commands to your language. Names AND descriptions. One command to patch, one to restore.

- **312 translation entries** — commands, UI strings, spinners, prompts, errors, labels
- **Winget native binary support** — byte-length-aware translation engine (307/312 verified)
- **Hot update detection** — notifies when Claude Code updates and translations need refreshing
- Works with both `npm` and `winget` installations
- Currently supports Traditional Chinese; adding a language = adding a `translations-xx.json` file

```bash
cd claude-i18n
python patch.py          # Apply translations
python patch.py --scan   # Find new untranslated commands
python patch.py --restore  # Revert to original
```

### self-guard — Config-Driven Behavior Detection (OVERHAULED)

- Migrated from non-existent `PreResponse` hook to the correct `Stop` hook
- Now fully config-driven via `self-guard-config.json` — no more hardcoded patterns
- Added Chinese language pattern support across all 4 detection modes
- 4 modes: Ask-instead-of-do, Acknowledge-without-action, Sycophancy, Passive waiting

### claude-whisper — Bug Fix

- Fixed: validate hook source file exists before attempting install

---

## Full Toolkit (7 tools)

| Tool | Type | Description |
|------|------|-------------|
| [claude-whisper](claude-whisper/) | Hook (Node.js) | Dynamic runtime instructions — inject behavior mid-session without restart |
| [claude-i18n](claude-i18n/) | Patcher (Python) | Localize all Claude Code commands and UI to your language |
| [self-guard](hooks/) | Hook (Python) | Detect bad AI behavior — sycophancy, asking instead of doing, passive waiting |
| [frost-scheduler](tools/frost-scheduler/) | Daemon (Python) | Session-aware task scheduler with ack tracking and pending queue |
| [frost-collab](tools/frost-collab/) | Tool (Python) | Multi-AI collaboration — shared task board, priority queue, dependencies |
| [memory-gc](tools/memory-gc.py) | Tool (Python) | Memory lifecycle — TTL, garbage collection, deduplication, contradiction detection |
| [pitfall-tracker](tools/pitfall-tracker.py) | Tool (Python) | Track AI mistakes, detect recurring patterns, escalation system |

## Install

```bash
# claude-whisper (npm)
npm install -g claude-whisper

# Everything else — clone and copy
git clone https://github.com/dead1786/permafrost-tools.git
```

See [README](README.md) for detailed setup instructions per tool.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full list of changes.
```

---

## Pre-Release Checklist

- [ ] Verify all tools work on clean machine
- [ ] Tag: `git tag -a v0.3.0 -m "v0.3.0 — claude-i18n, self-guard overhaul"`
- [ ] Push tag: `git push origin v0.3.0`
- [ ] Create GitHub release from tag with body above
- [ ] Verify claude-whisper npm package is up to date (v1.0.0)
- [ ] Check LICENSE year is correct (2026 ✓)
- [ ] SECURITY.md is committed
- [ ] CHANGELOG.md is committed

## gh Command to Create Release

```bash
gh release create v0.3.0 \
  --repo dead1786/permafrost-tools \
  --title "v0.3.0 — claude-i18n, self-guard overhaul, 7 tools" \
  --notes-file RELEASE_BODY.md
```

(Copy the release body above into RELEASE_BODY.md, or use `--notes` with heredoc.)
