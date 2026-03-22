# Permafrost Tools

Battle-tested utilities for Claude Code (and other AI coding assistants). Born from running a multi-agent AI team in production — every tool here exists because we hit a real problem and built a real fix.

No fluff. No frameworks. Just drop-in Python scripts that make your AI assistant more disciplined, self-aware, and reliable.

## What's Inside

### Hooks

| Tool | What It Does |
|------|-------------|
| **[self-guard](hooks/)** | PreResponse hook that detects bad AI behavior — sycophancy, asking instead of doing, acknowledging without acting, passive deferral. Catches the patterns before they reach you. |

### Tools

| Tool | What It Does |
|------|-------------|
| **[memory-gc](tools/memory-gc.py)** | Memory lifecycle manager with TTL, garbage collection, deduplication, contradiction detection, and promotion. Your AI's memories expire, get cleaned up, and only the important ones survive. |
| **[pitfall-tracker](tools/pitfall-tracker.py)** | Track AI mistakes, auto-detect recurring patterns, and generate improvement plans. 3 occurrences = flagged. 5 = escalated. Still happening? Human review. |

## Quick Start

### Self-Guard Hook

```bash
# Copy to your hooks directory
cp hooks/self-guard.py hooks/self-guard-config.json ~/.claude/hooks/

# Add to settings.json
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

Now your AI gets a warning injection every time it tries to ask "want me to...?" instead of just doing the work.

### Memory GC

```bash
# Copy to wherever you keep scripts
cp tools/memory-gc.py ~/scripts/

# Add a memory
python memory-gc.py add --type context --key "api_uses_rest" --value "This project uses REST, not GraphQL" --importance 3

# Run garbage collection (clean expired memories)
python memory-gc.py gc

# Check for contradictions and duplicates
python memory-gc.py validate

# Promote frequently-accessed memories
python memory-gc.py promote --key "api_uses_rest"

# Search
python memory-gc.py search --query "API"

# See statistics
python memory-gc.py stats
```

### Pitfall Tracker

```bash
cp tools/pitfall-tracker.py ~/scripts/

# Record a mistake
python pitfall-tracker.py add \
  --what "Used stale data for code review" \
  --cause "Didn't refresh file before reviewing" \
  --prevention "Always re-read files before commenting on them"

# Scan for recurring patterns and generate improvement items
python pitfall-tracker.py scan

# See all pitfalls
python pitfall-tracker.py list

# See pending improvements
python pitfall-tracker.py evolve

# Mark an improvement as done
python pitfall-tracker.py done --id evo-001

# Statistics
python pitfall-tracker.py stats
```

## Philosophy

1. **Code over prompts.** A hook that physically blocks bad behavior beats a rule in CLAUDE.md that gets ignored after compact.
2. **Decay is a feature.** Memories should expire. Old context pollutes new decisions. GC keeps things clean.
3. **Mistakes are data.** Track them, count them, escalate them. "I'll try harder" doesn't work — systematic prevention does.
4. **Zero dependencies.** Python 3.8+ standard library only. Copy a file, run it, done.
5. **Works with any AI.** Built for Claude Code, but the patterns are universal. Adapt the config for Cursor, Copilot, Aider, or whatever you use.

## Requirements

- Python 3.8+
- Claude Code (for hooks) or any AI assistant that supports similar hook mechanisms

## Configuration

Each tool is configurable:

- **self-guard**: Edit `self-guard-config.json` to add/remove/customize behavior patterns
- **memory-gc**: Use `--config` flag or edit `~/.claude/memory-gc-config.json` for TTL values and thresholds
- **pitfall-tracker**: Use `--pitfalls` and `--queue` flags to customize file locations, `--threshold` for recurrence sensitivity

## Adding Your Own Tools

This is a living toolkit. To add a new tool:

1. Drop a `.py` file in `hooks/` (for Claude Code hooks) or `tools/` (for standalone utilities)
2. Follow the pattern: zero dependencies, configurable, well-documented CLI
3. Submit a PR

## Background

These tools were built while managing a team of 7+ AI agents running 24/7 across multiple terminals. The problems they solve — AI sycophancy, memory pollution, recurring mistakes — are universal to anyone using AI coding assistants seriously.

If your AI keeps making the same mistakes, keeps agreeing with everything you say, or keeps "forgetting" things after context compression — these tools are for you.

## License

MIT
