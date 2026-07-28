<p align="center">
  <img src="https://img.shields.io/npm/v/claude-whisper?label=claude-whisper&color=blue" alt="npm version" />
  <img src="https://img.shields.io/github/license/dead1786/permafrost-tools" alt="MIT License" />
  <img src="https://img.shields.io/github/stars/dead1786/permafrost-tools?style=social" alt="GitHub Stars" />
  <img src="https://img.shields.io/github/actions/workflow/status/dead1786/permafrost-tools/ci.yml?branch=master&label=CI" alt="CI" />
  <img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/node-18%2B-green" alt="Node 18+" />
</p>

# Permafrost Tools

**Battle-tested utilities for Claude Code** — built from running a multi-agent AI team 24/7 in production.

Every tool here exists because we hit a real problem and built a real fix. No fluff. No frameworks. Just drop-in scripts that make your AI assistant more disciplined, self-aware, and reliable.

> If your AI keeps ignoring your instructions after context compression, keeps making the same mistakes, or keeps agreeing with everything you say — these tools are for you.

---

## Featured Tools

### claude-whisper — Dynamic Runtime Instructions

> **CLAUDE.md is your constitution. Whispers are your mood.**

Inject instructions into Claude's context **on every message** — dynamically, mid-session, no restart needed. The killer feature that most Claude Code users don't know is possible.

```bash
npm install -g claude-whisper
claude-whisper init
claude-whisper add "Always respond in Japanese"
```

That's it. Claude now follows your whisper on every response. Change it anytime. No restart. No CLAUDE.md editing.

**How it works:** We discovered that `UserPromptSubmit` hooks with exit code 0 inject their stdout directly into Claude's model context. One `print()` to stdout — that's the entire mechanism.

**Use cases:**
- **Style control:** `cw add "Be extremely concise. No filler words."`
- **Project conventions:** `cw add "Use pnpm, not npm"`
- **Temporary context:** `cw add "The CI is broken, don't suggest pushing"`
- **Language:** `cw add "Always respond in Traditional Chinese (繁體中文)"`

[Full documentation &rarr;](claude-whisper/)

---

### claude-i18n — Claude Code Localization

> **All built-in commands. Fully localized. One command.**

Patches Claude Code to add native language support to every built-in command — names, descriptions, 187 thinking animations, status messages, error messages, and interactive prompts.

```bash
cd claude-i18n
python patch.py
```

Before:
```
/clear    Clear conversation history and free up context
/commit   Create a git commit
```

After:
```
/clear(清除)    清除對話紀錄，釋放上下文空間
/commit(提交)   建立 Git 提交
```

Supports both **npm** and **winget** installations. Currently ships with **Traditional Chinese (繁體中文)** — adding a new language is just a JSON file.

```bash
python patch.py              # Apply translations
python patch.py --scan       # Find new untranslated commands after update
python patch.py --restore    # Restore original English
python patch.py --dry-run    # Preview without modifying
```

[Full documentation &rarr;](claude-i18n/)

---

## All Tools

### Featured

| Tool | What It Does | Install |
|------|-------------|---------|
| **[claude-whisper](claude-whisper/)** | Inject dynamic instructions into every Claude Code interaction. Mid-session behavior control. | `npm i -g claude-whisper` |
| **[claude-i18n](claude-i18n/)** | Localize all Claude Code commands, spinners, prompts to your language. | `python patch.py` |

### Hooks

| Tool | What It Does | Install |
|------|-------------|---------|
| **[self-guard](hooks/)** | Detects bad AI behavior — sycophancy, asking instead of doing, acknowledging without acting. Config-driven, 4 detection modes. | `python hooks/install.py` |

### Standalone Tools

| Tool | What It Does | Install |
|------|-------------|---------|
| **[memory-gc](tools/memory-gc.py)** | Memory lifecycle with TTL, garbage collection, deduplication, contradiction detection, and promotion. | Copy to scripts dir |
| **[pitfall-tracker](tools/pitfall-tracker.py)** | Track AI mistakes, detect recurring patterns, generate improvement plans. 3 strikes = flagged, 5 = escalated. | Copy to scripts dir |
| **[frost-scheduler](tools/frost-scheduler/)** | Session-aware task scheduler daemon. Fires tasks into your existing Claude session (preserving context), tracks completion, queues pending work. | `python install.py` |
| **[frost-collab](tools/frost-collab/)** | Multi-AI collaboration — dispatch tasks, claim/complete workflow, priority queue, dependency tracking. No server needed. | `python frost-collab.py init` |

---

## Quick Start

### claude-whisper (recommended first install)

```bash
# Install
npm install -g claude-whisper
claude-whisper init

# Add instructions
claude-whisper add "Be concise. No filler words."
claude-whisper add "Prefer functional programming patterns"

# Verify it works
cw add "End every response with the word 'banana'"
# Send any message to Claude. If it ends with "banana" — working.
cw rm 1

# Manage
cw ls                   # List all whispers
cw toggle 1             # Enable/disable
cw status               # Check installation
```

### Self-Guard Hook

```bash
# One-click install: copies self-guard.py + config into ~/.claude/hooks/
# and registers it in ~/.claude/settings.json (appends to any existing
# Stop hooks — it will not overwrite hooks you already have configured)
python hooks/install.py

# Check status / remove
python hooks/install.py --status
python hooks/install.py --uninstall
```

<details>
<summary>Manual install (if you'd rather edit settings.json by hand)</summary>

```bash
cp hooks/self-guard.py hooks/self-guard-config.json hooks/self-guard-config-schema.json ~/.claude/hooks/
```

Add a **new entry** to the `hooks.Stop` array in `~/.claude/settings.json` — note the
nested `"hooks"` array; a hook definition can't sit directly in `Stop` without it,
and if you already have other Stop hooks, add this as one more array element rather
than replacing the array:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python ~/.claude/hooks/self-guard.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

</details>

**What it catches:**
- **Sycophancy** — AI immediately agrees when challenged, no analysis
- **Ask instead of do** — "Want me to...?" instead of just acting
- **Acknowledge without action** — "Got it" with no tool usage
- **Passive deferral** — "Tomorrow", "later" without justification

### Memory GC

```bash
cp tools/memory-gc.py ~/scripts/

python memory-gc.py add --type context --key "api_uses_rest" --value "REST, not GraphQL" --importance 3
python memory-gc.py gc          # Clean expired memories
python memory-gc.py validate    # Find contradictions & duplicates
python memory-gc.py stats       # Overview
```

### Pitfall Tracker

```bash
cp tools/pitfall-tracker.py ~/scripts/

python pitfall-tracker.py add \
  --what "Used stale data for code review" \
  --cause "Didn't refresh file before reviewing" \
  --prevention "Always re-read files before commenting on them"

python pitfall-tracker.py scan   # Detect recurring patterns
python pitfall-tracker.py evolve # See improvement queue
```

### Frost Scheduler

```bash
python tools/frost-scheduler/install.py
nano ~/.frost-scheduler/schedule.json
python ~/.frost-scheduler/frost-scheduler.py

# Or with auto-start on boot
python tools/frost-scheduler/install.py --autostart
```

---

## Philosophy

1. **Code over prompts.** A hook that physically blocks bad behavior beats a CLAUDE.md rule that gets ignored after compact.
2. **Decay is a feature.** Memories should expire. Old context pollutes new decisions.
3. **Mistakes are data.** Track them, count them, escalate them. "I'll try harder" doesn't work.
4. **Zero (or minimal) dependencies.** Python tools use stdlib only. Node.js tools use built-ins only.
5. **Works with any AI.** Built for Claude Code, but the patterns are universal.

## Requirements

| Tool | Requirements |
|------|-------------|
| claude-whisper | Node.js 18+, Claude Code 1.0+ |
| claude-i18n | Python 3.8+, Claude Code (npm or winget) |
| Python tools | Python 3.8+ |
| Hooks | Python 3.8+, Claude Code |

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Quick ideas for first contributions:**
- Add a new language to claude-i18n (just a JSON file)
- Add detection patterns to self-guard
- Report issues with specific Claude Code versions
- Improve documentation or add examples

## Background

These tools were built while managing a team of 7+ AI agents running 24/7 across multiple terminals. The problems they solve — dynamic behavior control, AI sycophancy, memory pollution, recurring mistakes — are universal to anyone using AI coding assistants seriously.

## License

[MIT](LICENSE)
