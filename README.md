# Permafrost Tools

Battle-tested utilities for Claude Code (and other AI coding assistants). Born from running a multi-agent AI team in production — every tool here exists because we hit a real problem and built a real fix.

No fluff. No frameworks. Just drop-in scripts that make your AI assistant more disciplined, self-aware, and reliable.

---

## 🤫 claude-whisper — Dynamic Runtime Instructions

> **CLAUDE.md is your constitution. Whispers are your mood.**

The killer feature. Inject instructions into Claude's context **on every message** — dynamically, mid-session, no restart needed.

```bash
npm install -g claude-whisper
claude-whisper init
claude-whisper add "Always respond in Japanese"
```

That's it. Claude now follows your whisper on every response. Change it anytime. No restart. No CLAUDE.md editing.

**How we found this:** We dug into Claude Code's source and discovered that `UserPromptSubmit` hooks with exit code 0 inject their stdout directly into the model's context. One `print()` to stdout — that's the entire mechanism.

[Full documentation →](claude-whisper/)

---

## What's Inside

### Featured

| Tool | Language | What It Does |
|------|----------|-------------|
| **[claude-whisper](claude-whisper/)** | Node.js | 🤫 Inject dynamic instructions into every Claude Code interaction. Mid-session behavior control without restarting. |

### Hooks

| Tool | Language | What It Does |
|------|----------|-------------|
| **[self-guard](hooks/)** | Python | Detects bad AI behavior — sycophancy, asking instead of doing, acknowledging without acting. Catches the patterns before they reach you. |

### Tools

| Tool | Language | What It Does |
|------|----------|-------------|
| **[memory-gc](tools/memory-gc.py)** | Python | Memory lifecycle manager with TTL, garbage collection, deduplication, contradiction detection, and promotion. |
| **[pitfall-tracker](tools/pitfall-tracker.py)** | Python | Track AI mistakes, auto-detect recurring patterns, and generate improvement plans. 3 strikes = flagged. 5 = escalated. |

## Quick Start

### claude-whisper (Node.js)

```bash
npm install -g claude-whisper
claude-whisper init
claude-whisper add "Be concise. No filler words."
```

Verify it works — add a test whisper and see if Claude obeys:

```bash
claude-whisper add "End every response with the word 'banana'"
# Send any message to Claude. If it ends with "banana" — it's working.
claude-whisper rm 1
```

[Full docs →](claude-whisper/)

### Self-Guard Hook (Python)

```bash
cp hooks/self-guard.py hooks/self-guard-config.json ~/.claude/hooks/
```

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreResponse": [
      {
        "type": "command",
        "command": "python ~/.claude/hooks/self-guard.py"
      }
    ]
  }
}
```

### Memory GC (Python)

```bash
cp tools/memory-gc.py ~/scripts/

python memory-gc.py add --type context --key "api_uses_rest" --value "REST, not GraphQL" --importance 3
python memory-gc.py gc          # Clean expired memories
python memory-gc.py validate    # Find contradictions & duplicates
python memory-gc.py stats       # Overview
```

### Pitfall Tracker (Python)

```bash
cp tools/pitfall-tracker.py ~/scripts/

python pitfall-tracker.py add \
  --what "Used stale data for code review" \
  --cause "Didn't refresh file before reviewing" \
  --prevention "Always re-read files before commenting on them"

python pitfall-tracker.py scan   # Detect recurring patterns
python pitfall-tracker.py evolve # See improvement queue
```

## Philosophy

1. **Code over prompts.** A hook that physically blocks bad behavior beats a rule in CLAUDE.md that gets ignored after compact.
2. **Decay is a feature.** Memories should expire. Old context pollutes new decisions. GC keeps things clean.
3. **Mistakes are data.** Track them, count them, escalate them. "I'll try harder" doesn't work — systematic prevention does.
4. **Zero (or minimal) dependencies.** Python tools use stdlib only. Node.js tools use built-ins only.
5. **Works with any AI.** Built for Claude Code, but the patterns are universal.

## Requirements

- **claude-whisper**: Node.js 18+, Claude Code 1.0+
- **Python tools**: Python 3.8+, Claude Code (for hooks)

## Configuration

- **claude-whisper**: `cw ls` / `cw toggle <id>` to manage whispers. Data in `~/.claude-whisper/`
- **self-guard**: Edit `self-guard-config.json` to customize behavior patterns
- **memory-gc**: `--config` flag or `~/.claude/memory-gc-config.json`
- **pitfall-tracker**: `--pitfalls` and `--queue` flags, `--threshold` for sensitivity

## Background

These tools were built while managing a team of 7+ AI agents running 24/7 across multiple terminals. The problems they solve — dynamic behavior control, AI sycophancy, memory pollution, recurring mistakes — are universal to anyone using AI coding assistants seriously.

If your AI keeps ignoring your instructions after context compression, keeps making the same mistakes, or keeps agreeing with everything you say — these tools are for you.

## License

MIT
