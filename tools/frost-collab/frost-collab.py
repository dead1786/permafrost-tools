#!/usr/bin/env python3
"""
frost-collab.py — Multi-AI Collaboration for Claude Code

Enables multiple Claude Code instances (agents) to collaborate on tasks:
  - Dispatch tasks from an orchestrator to worker agents
  - Workers claim tasks (no double-assignment)
  - Real-time status board visible to all agents
  - Automatic result aggregation
  - File-based (no server needed) — works on any OS

Usage:
  # Initialize a collaboration workspace
  python frost-collab.py init

  # Dispatch a task to available agents
  python frost-collab.py dispatch --title "Run tests" --prompt "Run pytest and report results" [--assign agent-name]

  # Agent claims next available task
  python frost-collab.py claim --agent frost

  # Agent reports progress
  python frost-collab.py progress --task-id abc123 --status "50% done, 12/24 tests passing"

  # Agent completes a task
  python frost-collab.py complete --task-id abc123 --result "All 24 tests passing"

  # Agent fails a task (returns to pool or escalates)
  python frost-collab.py fail --task-id abc123 --reason "Missing dependency"

  # View the collaboration board
  python frost-collab.py board

  # Aggregate all completed results
  python frost-collab.py aggregate [--since 2h]

  # List agents and their current workload
  python frost-collab.py agents

  # Register an agent
  python frost-collab.py register --agent frost --capabilities "code,test,deploy"

  # Cancel a pending/in-progress task
  python frost-collab.py cancel --task-id abc123

Environment variables:
  FROST_COLLAB_DIR  — Path to collaboration workspace (default: ~/.frost-collab/)

Requires: Python 3.8+, no external dependencies.
"""

__version__ = "1.0.0"

import argparse
import json
import os
import sys
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# === CONFIGURATION ===
DEFAULT_COLLAB_DIR = os.path.join(os.path.expanduser("~"), ".frost-collab")
COLLAB_DIR = os.environ.get("FROST_COLLAB_DIR", DEFAULT_COLLAB_DIR)

TASKS_DIR = os.path.join(COLLAB_DIR, "tasks")
AGENTS_FILE = os.path.join(COLLAB_DIR, "agents.json")
BOARD_FILE = os.path.join(COLLAB_DIR, "board.json")
LOG_FILE = os.path.join(COLLAB_DIR, "collab.log")


# === FILE LOCKING (cross-platform) ===
class FileLock:
    """Simple file-based lock. Works on Windows and Unix."""

    def __init__(self, path):
        self.lock_path = path + ".lock"
        self.fd = None

    def acquire(self, timeout=5):
        start = time.time()
        while True:
            try:
                self.fd = open(self.lock_path, "x")
                # Write PID for debugging
                self.fd.write(str(os.getpid()))
                self.fd.flush()
                return True
            except FileExistsError:
                # Check if lock is stale (>60s old)
                try:
                    age = time.time() - os.path.getmtime(self.lock_path)
                    if age > 60:
                        os.remove(self.lock_path)
                        continue
                except OSError:
                    pass
                if time.time() - start > timeout:
                    return False
                time.sleep(0.1)

    def release(self):
        if self.fd:
            self.fd.close()
            self.fd = None
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock: {self.lock_path}")
        return self

    def __exit__(self, *args):
        self.release()


# === UTILITIES ===
def gen_task_id():
    """Generate a short unique task ID."""
    raw = f"{time.time()}-{os.getpid()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def log(msg):
    ts = now_iso()
    line = f"[{ts}] {msg}"
    os.makedirs(COLLAB_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_task(task_id):
    path = os.path.join(TASKS_DIR, f"{task_id}.json")
    return read_json(path)


def save_task(task_id, data):
    path = os.path.join(TASKS_DIR, f"{task_id}.json")
    write_json(path, data)


def load_all_tasks():
    tasks = []
    if not os.path.isdir(TASKS_DIR):
        return tasks
    for fname in os.listdir(TASKS_DIR):
        if fname.endswith(".json") and not fname.endswith(".lock"):
            t = read_json(os.path.join(TASKS_DIR, fname))
            if t:
                tasks.append(t)
    return tasks


def load_agents():
    return read_json(AGENTS_FILE, default={"agents": {}}).get("agents", {})


def save_agents(agents):
    write_json(AGENTS_FILE, {"agents": agents, "updated": now_iso()})


# === COMMANDS ===
def cmd_init(args):
    """Initialize collaboration workspace."""
    os.makedirs(TASKS_DIR, exist_ok=True)
    if not os.path.exists(AGENTS_FILE):
        save_agents({})
    if not os.path.exists(BOARD_FILE):
        write_json(BOARD_FILE, {"tasks": [], "updated": now_iso()})
    log("Workspace initialized")
    print(f"frost-collab workspace initialized at {COLLAB_DIR}")
    print(f"  Tasks:  {TASKS_DIR}/")
    print(f"  Agents: {AGENTS_FILE}")
    print(f"  Board:  {BOARD_FILE}")


def cmd_register(args):
    """Register an agent."""
    lock = FileLock(AGENTS_FILE)
    with lock:
        agents = load_agents()
        caps = [c.strip() for c in args.capabilities.split(",")] if args.capabilities else []
        agents[args.agent] = {
            "name": args.agent,
            "capabilities": caps,
            "registered": now_iso(),
            "last_seen": now_iso(),
            "current_task": None,
            "completed_count": agents.get(args.agent, {}).get("completed_count", 0),
        }
        save_agents(agents)
    log(f"Agent registered: {args.agent} caps={caps}")
    print(f"Agent '{args.agent}' registered with capabilities: {caps}")


def cmd_dispatch(args):
    """Dispatch a new task."""
    task_id = gen_task_id()
    task = {
        "id": task_id,
        "title": args.title,
        "prompt": args.prompt,
        "status": "pending",
        "priority": args.priority,
        "assigned_to": args.assign,
        "created": now_iso(),
        "updated": now_iso(),
        "claimed_at": None,
        "completed_at": None,
        "progress": [],
        "result": None,
        "fail_reason": None,
        "tags": [t.strip() for t in args.tags.split(",")] if args.tags else [],
        "depends_on": [d.strip() for d in args.depends.split(",")] if args.depends else [],
    }

    if args.assign:
        task["status"] = "assigned"

    save_task(task_id, task)
    _refresh_board()
    log(f"Task dispatched: {task_id} '{args.title}' assign={args.assign}")
    print(f"Task dispatched: {task_id}")
    print(f"  Title:    {args.title}")
    print(f"  Status:   {task['status']}")
    if args.assign:
        print(f"  Assigned: {args.assign}")


def cmd_claim(args):
    """Agent claims the next available task."""
    agent_name = args.agent
    tasks = load_all_tasks()

    # Sort by priority (higher first), then by creation time
    available = [t for t in tasks if t["status"] == "pending" or
                 (t["status"] == "assigned" and t["assigned_to"] == agent_name)]

    # Check dependencies
    completed_ids = {t["id"] for t in tasks if t["status"] == "completed"}
    claimable = []
    for t in available:
        deps = t.get("depends_on", [])
        if all(d in completed_ids for d in deps):
            claimable.append(t)

    claimable.sort(key=lambda t: (-t.get("priority", 0), t["created"]))

    if not claimable:
        print("No tasks available to claim.")
        return

    task = claimable[0]
    task_id = task["id"]

    lock = FileLock(os.path.join(TASKS_DIR, f"{task_id}.json"))
    with lock:
        # Re-read to avoid race
        task = load_task(task_id)
        if task["status"] not in ("pending", "assigned"):
            print(f"Task {task_id} already claimed by someone else.")
            return

        task["status"] = "in_progress"
        task["assigned_to"] = agent_name
        task["claimed_at"] = now_iso()
        task["updated"] = now_iso()
        save_task(task_id, task)

    # Update agent
    alock = FileLock(AGENTS_FILE)
    with alock:
        agents = load_agents()
        if agent_name in agents:
            agents[agent_name]["current_task"] = task_id
            agents[agent_name]["last_seen"] = now_iso()
            save_agents(agents)

    _refresh_board()
    log(f"Task claimed: {task_id} by {agent_name}")
    print(f"Claimed task: {task_id}")
    print(f"  Title:  {task['title']}")
    print(f"  Prompt: {task['prompt']}")


def cmd_progress(args):
    """Report progress on a task."""
    task_id = args.task_id
    lock = FileLock(os.path.join(TASKS_DIR, f"{task_id}.json"))
    with lock:
        task = load_task(task_id)
        if not task:
            print(f"Task {task_id} not found.")
            return
        task["progress"].append({
            "timestamp": now_iso(),
            "message": args.status,
        })
        task["updated"] = now_iso()
        save_task(task_id, task)

    _refresh_board()
    log(f"Progress on {task_id}: {args.status}")
    print(f"Progress recorded for {task_id}")


def cmd_complete(args):
    """Mark a task as completed."""
    task_id = args.task_id
    lock = FileLock(os.path.join(TASKS_DIR, f"{task_id}.json"))
    with lock:
        task = load_task(task_id)
        if not task:
            print(f"Task {task_id} not found.")
            return
        task["status"] = "completed"
        task["result"] = args.result
        task["completed_at"] = now_iso()
        task["updated"] = now_iso()
        agent_name = task.get("assigned_to")
        save_task(task_id, task)

    # Update agent stats
    if agent_name:
        alock = FileLock(AGENTS_FILE)
        with alock:
            agents = load_agents()
            if agent_name in agents:
                agents[agent_name]["current_task"] = None
                agents[agent_name]["completed_count"] = agents[agent_name].get("completed_count", 0) + 1
                agents[agent_name]["last_seen"] = now_iso()
                save_agents(agents)

    _refresh_board()
    log(f"Task completed: {task_id} by {agent_name}")
    print(f"Task {task_id} completed.")


def cmd_fail(args):
    """Mark a task as failed."""
    task_id = args.task_id
    lock = FileLock(os.path.join(TASKS_DIR, f"{task_id}.json"))
    with lock:
        task = load_task(task_id)
        if not task:
            print(f"Task {task_id} not found.")
            return
        task["status"] = "failed"
        task["fail_reason"] = args.reason
        task["updated"] = now_iso()
        agent_name = task.get("assigned_to")
        save_task(task_id, task)

    if agent_name:
        alock = FileLock(AGENTS_FILE)
        with alock:
            agents = load_agents()
            if agent_name in agents:
                agents[agent_name]["current_task"] = None
                agents[agent_name]["last_seen"] = now_iso()
                save_agents(agents)

    _refresh_board()
    log(f"Task failed: {task_id} reason={args.reason}")
    print(f"Task {task_id} marked as failed: {args.reason}")


def cmd_cancel(args):
    """Cancel a task."""
    task_id = args.task_id
    lock = FileLock(os.path.join(TASKS_DIR, f"{task_id}.json"))
    with lock:
        task = load_task(task_id)
        if not task:
            print(f"Task {task_id} not found.")
            return
        task["status"] = "cancelled"
        task["updated"] = now_iso()
        save_task(task_id, task)

    _refresh_board()
    log(f"Task cancelled: {task_id}")
    print(f"Task {task_id} cancelled.")


def cmd_board(args):
    """Display the collaboration board."""
    tasks = load_all_tasks()
    if not tasks:
        print("No tasks. Use 'frost-collab dispatch' to create one.")
        return

    # Group by status
    groups = {"pending": [], "assigned": [], "in_progress": [], "completed": [], "failed": [], "cancelled": []}
    for t in tasks:
        s = t.get("status", "pending")
        if s in groups:
            groups[s].append(t)

    status_icons = {
        "pending": "[WAIT]",
        "assigned": "[ASGN]",
        "in_progress": "[WORK]",
        "completed": "[DONE]",
        "failed": "[FAIL]",
        "cancelled": "[CNCL]",
    }

    print("=" * 60)
    print("  FROST-COLLAB BOARD")
    print("=" * 60)

    for status in ["in_progress", "assigned", "pending", "completed", "failed", "cancelled"]:
        items = groups[status]
        if not items:
            continue
        print(f"\n--- {status.upper()} ({len(items)}) ---")
        for t in sorted(items, key=lambda x: (-x.get("priority", 0), x["created"])):
            icon = status_icons.get(status, "[???]")
            agent = t.get("assigned_to") or "unassigned"
            pri = f"P{t.get('priority', 0)}" if t.get("priority", 0) > 0 else ""
            print(f"  {icon} {t['id']}  {pri:>3}  {t['title'][:40]:<40}  @{agent}")
            if t.get("progress"):
                last = t["progress"][-1]
                print(f"         -> {last['message'][:50]}")

    print(f"\n{'=' * 60}")
    total = len(tasks)
    done = len(groups["completed"])
    active = len(groups["in_progress"])
    print(f"  Total: {total}  |  Active: {active}  |  Done: {done}  |  Pending: {len(groups['pending'])}")
    print(f"{'=' * 60}")


def cmd_aggregate(args):
    """Aggregate completed task results."""
    tasks = load_all_tasks()
    completed = [t for t in tasks if t["status"] == "completed"]

    if args.since:
        cutoff = _parse_since(args.since)
        completed = [t for t in completed if t.get("completed_at", "") >= cutoff]

    if not completed:
        print("No completed tasks to aggregate.")
        return

    completed.sort(key=lambda t: t.get("completed_at", ""))
    print(f"Completed tasks ({len(completed)}):\n")
    for t in completed:
        print(f"[{t['id']}] {t['title']}")
        print(f"  Agent: {t.get('assigned_to', '?')}")
        print(f"  Done:  {t.get('completed_at', '?')}")
        if t.get("result"):
            print(f"  Result: {t['result']}")
        print()


def cmd_agents(args):
    """List registered agents."""
    agents = load_agents()
    if not agents:
        print("No agents registered. Use 'frost-collab register --agent <name>'")
        return

    print(f"{'Agent':<15} {'Capabilities':<30} {'Task':<10} {'Done':<5} {'Last Seen'}")
    print("-" * 80)
    for name, info in sorted(agents.items()):
        caps = ", ".join(info.get("capabilities", []))[:28]
        task = info.get("current_task") or "-"
        done = info.get("completed_count", 0)
        seen = info.get("last_seen", "?")[11:19] if info.get("last_seen") else "?"
        print(f"{name:<15} {caps:<30} {task:<10} {done:<5} {seen}")


def _refresh_board():
    """Update the board summary file."""
    tasks = load_all_tasks()
    summary = []
    for t in tasks:
        summary.append({
            "id": t["id"],
            "title": t["title"],
            "status": t["status"],
            "assigned_to": t.get("assigned_to"),
            "priority": t.get("priority", 0),
            "updated": t.get("updated"),
        })
    write_json(BOARD_FILE, {"tasks": summary, "updated": now_iso()})


def _parse_since(since_str):
    """Parse '2h', '1d', '30m' into ISO datetime string."""
    unit = since_str[-1]
    val = int(since_str[:-1])
    if unit == "h":
        delta = timedelta(hours=val)
    elif unit == "d":
        delta = timedelta(days=val)
    elif unit == "m":
        delta = timedelta(minutes=val)
    else:
        delta = timedelta(hours=val)
    cutoff = datetime.now() - delta
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S")


# === MAIN ===
def main():
    parser = argparse.ArgumentParser(
        description="frost-collab — Multi-AI Collaboration for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"frost-collab {__version__}")

    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="Initialize collaboration workspace")

    # register
    p = sub.add_parser("register", help="Register an agent")
    p.add_argument("--agent", required=True, help="Agent name")
    p.add_argument("--capabilities", default="", help="Comma-separated capabilities")

    # dispatch
    p = sub.add_parser("dispatch", help="Dispatch a task")
    p.add_argument("--title", required=True, help="Task title")
    p.add_argument("--prompt", required=True, help="Task prompt/instructions")
    p.add_argument("--assign", default=None, help="Assign to specific agent")
    p.add_argument("--priority", type=int, default=0, help="Priority (higher = first)")
    p.add_argument("--tags", default="", help="Comma-separated tags")
    p.add_argument("--depends", default="", help="Comma-separated task IDs this depends on")

    # claim
    p = sub.add_parser("claim", help="Claim next available task")
    p.add_argument("--agent", required=True, help="Agent name")

    # progress
    p = sub.add_parser("progress", help="Report task progress")
    p.add_argument("--task-id", required=True, help="Task ID")
    p.add_argument("--status", required=True, help="Progress message")

    # complete
    p = sub.add_parser("complete", help="Complete a task")
    p.add_argument("--task-id", required=True, help="Task ID")
    p.add_argument("--result", required=True, help="Result summary")

    # fail
    p = sub.add_parser("fail", help="Fail a task")
    p.add_argument("--task-id", required=True, help="Task ID")
    p.add_argument("--reason", required=True, help="Failure reason")

    # cancel
    p = sub.add_parser("cancel", help="Cancel a task")
    p.add_argument("--task-id", required=True, help="Task ID")

    # board
    sub.add_parser("board", help="Show collaboration board")

    # aggregate
    p = sub.add_parser("aggregate", help="Aggregate completed results")
    p.add_argument("--since", default=None, help="Time filter (e.g. 2h, 1d)")

    # agents
    sub.add_parser("agents", help="List registered agents")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmd_map = {
        "init": cmd_init,
        "register": cmd_register,
        "dispatch": cmd_dispatch,
        "claim": cmd_claim,
        "progress": cmd_progress,
        "complete": cmd_complete,
        "fail": cmd_fail,
        "cancel": cmd_cancel,
        "board": cmd_board,
        "aggregate": cmd_aggregate,
        "agents": cmd_agents,
    }

    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
