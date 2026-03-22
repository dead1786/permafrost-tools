#!/usr/bin/env python3
"""
frost-ack.py — Task acknowledgment tracker for frost-scheduler

Tracks whether AI tasks were actually completed, not just dispatched.
The scheduler writes .pending files; the AI calls `ack` when done.
External watchdogs can `check` to verify completion.

Usage:
  python frost-ack.py pending <task_id>          # Mark task as dispatched
  python frost-ack.py ack <task_id>              # Mark task as completed
  python frost-ack.py check <task_id> [max_age]  # Verify (exit 0=ok, 1=no ack, 2=stale)
  python frost-ack.py status                     # Show all ack states
  python frost-ack.py clean [max_age_hours]      # Remove old ack files (default: 48h)

Environment variables:
  FROST_SCHEDULER_CONFIG  — Config directory (default: ~/.frost-scheduler/)
"""

import json
import os
import sys
import time
from datetime import datetime

CONFIG_DIR = os.environ.get(
    "FROST_SCHEDULER_CONFIG",
    os.path.join(os.path.expanduser("~"), ".frost-scheduler"),
)
ACK_DIR = os.path.join(CONFIG_DIR, "ack")
os.makedirs(ACK_DIR, exist_ok=True)


def pending(task_id):
    """Mark a task as dispatched (waiting for ack)."""
    path = os.path.join(ACK_DIR, f"{task_id}.pending")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"time": datetime.now().isoformat(), "task": task_id}, f)
    print(f"pending: {task_id}")


def ack(task_id):
    """Mark a task as completed."""
    path = os.path.join(ACK_DIR, f"{task_id}.ack")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"time": datetime.now().isoformat(), "task": task_id}, f)
    # Clear pending marker
    pending_path = os.path.join(ACK_DIR, f"{task_id}.pending")
    if os.path.exists(pending_path):
        os.remove(pending_path)
    print(f"ack: {task_id}")


def check(task_id, max_stale_sec=None):
    """Check ack status. Returns exit code: 0=ok, 1=no ack, 2=stale."""
    ack_path = os.path.join(ACK_DIR, f"{task_id}.ack")
    pending_path = os.path.join(ACK_DIR, f"{task_id}.pending")

    if os.path.exists(ack_path):
        age = time.time() - os.path.getmtime(ack_path)
        if max_stale_sec and age > max_stale_sec:
            print(f"stale: {task_id} (ack {age:.0f}s old, max {max_stale_sec}s)")
            return 2
        print(f"ok: {task_id} (ack {age:.0f}s old)")
        return 0
    elif os.path.exists(pending_path):
        age = time.time() - os.path.getmtime(pending_path)
        print(f"pending: {task_id} (waiting {age:.0f}s)")
        return 1
    else:
        print(f"no_record: {task_id}")
        return 1


def status():
    """List all ack states."""
    if not os.path.exists(ACK_DIR):
        print("No ack directory found")
        return
    files = sorted(os.listdir(ACK_DIR))
    if not files:
        print("No records")
        return

    print(f"\n{'Task ID':<30} {'State':<10} {'Age'}")
    print("-" * 55)
    for f in files:
        path = os.path.join(ACK_DIR, f)
        age = time.time() - os.path.getmtime(path)
        name, ext = os.path.splitext(f)
        state = ext[1:]  # "pending" or "ack"

        if age < 60:
            age_str = f"{age:.0f}s"
        elif age < 3600:
            age_str = f"{age/60:.0f}m"
        else:
            age_str = f"{age/3600:.1f}h"

        print(f"  {name:<28} {state:<10} {age_str} ago")


def clean(max_age_hours=48):
    """Remove ack files older than max_age_hours."""
    if not os.path.exists(ACK_DIR):
        return
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0
    for f in os.listdir(ACK_DIR):
        path = os.path.join(ACK_DIR, f)
        if os.path.getmtime(path) < cutoff:
            os.remove(path)
            removed += 1
    print(f"Cleaned {removed} old ack files (>{max_age_hours}h)")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]
    if cmd == "pending" and len(args) >= 2:
        pending(args[1])
    elif cmd == "ack" and len(args) >= 2:
        ack(args[1])
    elif cmd == "check" and len(args) >= 2:
        max_stale = int(args[2]) if len(args) >= 3 else None
        sys.exit(check(args[1], max_stale))
    elif cmd == "status":
        status()
    elif cmd == "clean":
        hours = float(args[1]) if len(args) >= 2 else 48
        clean(hours)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
