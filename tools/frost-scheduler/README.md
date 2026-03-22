# frost-scheduler

Session-aware task scheduler for Claude Code. A persistent daemon that schedules tasks, tracks completion, queues pending work, and wakes your AI assistant — without losing conversation context.

## Why Not Just Use cron / Task Scheduler / claude-code-scheduler?

| Feature | cron / Task Scheduler | claude-code-scheduler | **frost-scheduler** |
|---------|----------------------|----------------------|-------------------|
| Session-aware | No — spawns new process | No — `claude -p` each time | **Yes** — injects into existing session via SendInput |
| Context preservation | None | None (fresh context per run) | **Full** — your AI keeps all conversation history |
| Task acknowledgment | No | No | **Yes** — tracks if tasks actually completed |
| Pending queue | No — missed = gone | No | **Yes** — tasks queue up, nothing lost |
| Night mode | Manual cron rules | No | **Built-in** — configurable quiet hours with longer intervals |
| Hot-reload | Requires restart | Requires restart | **Auto** — edit schedule.json, changes apply in 30s |
| Dependencies | OS-specific | Node.js | **Python stdlib only** (pywin32 optional on Windows) |

The key difference: **frost-scheduler was built to keep your AI's brain intact.** When cron runs `claude -p "do something"`, your AI wakes up with amnesia every time. frost-scheduler types directly into your existing terminal session, so your AI has full access to its conversation history, loaded files, and accumulated context.

## Quick Start

```bash
# One-line install
python install.py

# Edit your schedule
nano ~/.frost-scheduler/schedule.json

# Start the daemon
python ~/.frost-scheduler/frost-scheduler.py

# Or with auto-start on boot
python install.py --autostart
```

## How It Works

```
┌─────────────────────────────────────────────────┐
│  frost-scheduler daemon (polls every 30s)       │
│                                                  │
│  schedule.json ──► is_task_due() ──► execute()  │
│                                                  │
│  Script tasks:  subprocess.run(script.py)       │
│  AI tasks:      queue ──► wake backend ──► ack  │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ SendInput│ │claude -p │ │ Custom   │
    │(Windows) │ │(any OS)  │ │ Command  │
    └──────────┘ └──────────┘ └──────────┘
          │
          ▼
    ┌──────────────────────┐
    │ Your Claude session  │
    │ (context preserved!) │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ frost-ack.py ack     │
    │ (task confirmed done)│
    └──────────────────────┘
```

## Schedule Configuration

`~/.frost-scheduler/schedule.json`:

```json
{
  "trigger_text": "check schedule",
  "wake": {
    "method": "auto",
    "window_title": "claude"
  },
  "tasks": [
    {
      "id": "morning-briefing",
      "enabled": true,
      "schedule": {
        "type": "daily",
        "time": "08:00"
      },
      "command": "Good morning. Read TODOs and give me a status update.",
      "description": "Daily morning briefing"
    }
  ]
}
```

### Wake Methods

| Method | Platform | How |
|--------|----------|-----|
| `sendinput` | Windows | Types into a terminal window via Win32 API |
| `claude-cli` | Any | Runs `claude -p "message"` (new context each time) |
| `command` | Any | Runs your custom command with `{MESSAGE}` placeholder |
| `pending-only` | Any | Just queues — your AI polls `pending.json` |
| `auto` | Any | Windows → sendinput, else → pending-only |

Set via `wake.method` in schedule.json or `FROST_SCHEDULER_WAKE` env var.

### Schedule Types

**Daily** — fires once per day at specified time:
```json
{ "type": "daily", "time": "08:00" }
```

**Interval** — fires every N hours/minutes with optional night mode:
```json
{
  "type": "interval",
  "hours": 2,
  "night_hours": ["00:00", "06:00"],
  "night_interval_hours": 4,
  "start_after": "07:00",
  "stop_before": "23:00"
}
```

**Weekly** — fires on a specific day:
```json
{ "type": "weekly", "day": "friday", "time": "17:00" }
```

**Monthly** — fires on a specific day of month:
```json
{ "type": "monthly", "day_of_month": 1, "time": "09:00" }
```

**One-shot** — fires once then never again:
```json
{ "type": "daily", "time": "14:00", "once": true, "start_date": "2025-01-15" }
```

### Task Types

**AI tasks** — sends a command to your Claude session:
```json
{
  "id": "review-prs",
  "command": "Check open PRs and summarize any that need attention.",
  "schedule": { "type": "daily", "time": "09:00" }
}
```

**Script tasks** — runs a Python script silently:
```json
{
  "id": "backup-db",
  "script": "/path/to/backup.py",
  "script_args": ["--compress"],
  "schedule": { "type": "daily", "time": "03:00" }
}
```

**Shell tasks** — runs a shell command:
```json
{
  "id": "cleanup-logs",
  "script_shell": "find {HOME}/logs -name '*.log' -mtime +7 -delete",
  "schedule": { "type": "weekly", "day": "sunday", "time": "04:00" }
}
```

**Hybrid** — script + AI command:
```json
{
  "id": "health-report",
  "script": "collect-metrics.py",
  "command": "Read the latest metrics and alert me if anything is off.",
  "schedule": { "type": "interval", "hours": 1 }
}
```

## Ack System

The ack (acknowledgment) system tracks whether AI tasks were actually completed:

```bash
# Scheduler automatically writes .pending when dispatching
# Your AI should call this when the task is done:
python frost-ack.py ack morning-briefing

# Check if a task was completed:
python frost-ack.py check morning-briefing

# Check with max age (fail if ack older than 3600s):
python frost-ack.py check morning-briefing 3600

# See all ack states:
python frost-ack.py status

# Clean up old ack files:
python frost-ack.py clean 48
```

### Integrating Ack Into Your AI Workflow

Add this to your AI's instructions (CLAUDE.md or system prompt):

```markdown
When you see "[Scheduled]" in a message, it's from frost-scheduler.
After completing the task, run: `python ~/.frost-scheduler/frost-ack.py ack <task-id>`
```

## Pending Queue

When multiple tasks fire at once (e.g., after system wake from sleep), they queue in `pending.json`:

```json
[
  {"task_id": "morning-briefing", "command": "...", "queued_at": "2025-01-15T08:00:02"},
  {"task_id": "health-check", "command": "...", "queued_at": "2025-01-15T08:00:02"}
]
```

Your AI processes them in order. The queue prevents tasks from being lost even if the AI session is busy.

To read and clear the queue from your AI:

```python
import json
with open(os.path.expanduser("~/.frost-scheduler/pending.json")) as f:
    tasks = json.load(f)
# Process tasks...
with open(os.path.expanduser("~/.frost-scheduler/pending.json"), "w") as f:
    json.dump([], f)
```

## CLI Reference

```bash
# Daemon
python frost-scheduler.py              # Start daemon
python frost-scheduler.py --once       # Single check (testing)
python frost-scheduler.py --list       # Show tasks + status
python frost-scheduler.py --validate   # Validate schedule.json
python frost-scheduler.py --version    # Version info

# Ack
python frost-ack.py pending <id>       # Mark dispatched
python frost-ack.py ack <id>           # Mark completed
python frost-ack.py check <id> [age]   # Verify completion
python frost-ack.py status             # All states
python frost-ack.py clean [hours]      # Cleanup old files

# Install
python install.py                      # Setup config
python install.py --autostart          # Setup + auto-start
python install.py --config-only        # Config only
python install.py --uninstall          # Remove auto-start
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FROST_SCHEDULER_CONFIG` | `~/.frost-scheduler/` | Config directory path |
| `FROST_SCHEDULER_WAKE` | `auto` | Override wake method |

## Requirements

- Python 3.8+
- No dependencies (stdlib only)
- Windows SendInput wake: pywin32 not required (uses ctypes directly)

## License

MIT
