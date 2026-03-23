# frost-collab — Multi-AI Collaboration

Enable multiple Claude Code instances to collaborate on tasks without a server. Pure file-based coordination.

## The Problem

You have 3+ AI agents running in separate terminals. Agent A needs to delegate subtasks to Agent B and C, wait for results, then combine them. Today you do this manually — copy-pasting between terminals, tracking who's doing what in your head.

## The Solution

`frost-collab` provides a shared task board. Any agent can:
- **Dispatch** tasks (with priority, dependencies, tags)
- **Claim** the next available task (automatic, no double-assignment)
- **Report progress** in real-time
- **Complete/fail** tasks with results
- **View the board** to see what everyone is doing

All state lives in `~/.frost-collab/` — JSON files with file-level locking. No server, no database, no dependencies.

## Quick Start

```bash
# Initialize workspace (once)
python frost-collab.py init

# Register your agents
python frost-collab.py register --agent frost --capabilities "code,test,deploy"
python frost-collab.py register --agent jellyfish --capabilities "code,research"
python frost-collab.py register --agent mio --capabilities "trading,deploy"

# Dispatch a task
python frost-collab.py dispatch \
  --title "Run integration tests" \
  --prompt "Run pytest tests/integration/ and report failures" \
  --priority 2

# Agent claims next available task
python frost-collab.py claim --agent jellyfish

# Report progress
python frost-collab.py progress --task-id abc123 --status "12/24 tests passing"

# Complete the task
python frost-collab.py complete --task-id abc123 --result "All 24 tests passing"

# View the board
python frost-collab.py board
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize collaboration workspace |
| `register` | Register an agent with capabilities |
| `dispatch` | Create and dispatch a new task |
| `claim` | Agent claims next available task |
| `progress` | Report progress on a task |
| `complete` | Mark task as completed with result |
| `fail` | Mark task as failed with reason |
| `cancel` | Cancel a pending/in-progress task |
| `board` | Display the collaboration board |
| `aggregate` | Show all completed results |
| `agents` | List agents and workload |

## Task Lifecycle

```
pending --> assigned --> in_progress --> completed
                    \               \-> failed
                     \-> cancelled
```

## Features

- **Priority queue**: Higher priority tasks get claimed first
- **Dependencies**: Tasks can depend on other tasks (won't be claimable until deps complete)
- **File locking**: Safe concurrent access from multiple agents
- **Stale lock recovery**: Locks older than 60s are auto-cleaned
- **Progress tracking**: Agents can report incremental progress
- **Result aggregation**: Collect all completed results with time filters

## Configuration

Set `FROST_COLLAB_DIR` environment variable to change the workspace location (default: `~/.frost-collab/`).

## Integration with frost-scheduler

Use frost-scheduler to periodically trigger agents to check for new tasks:

```json
{
  "id": "collab-check",
  "schedule": "*/5 * * * *",
  "prompt": "Check frost-collab board: python ~/.frost-collab/../frost-collab.py claim --agent frost"
}
```

## Requirements

- Python 3.8+
- No external dependencies
