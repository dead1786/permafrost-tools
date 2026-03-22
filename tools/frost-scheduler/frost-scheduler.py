#!/usr/bin/env python3
"""
frost-scheduler.py — Session-aware task scheduler for Claude Code

A persistent daemon that schedules tasks, tracks completion via ack,
queues pending work, and wakes your AI assistant without losing context.

Unlike cron-style schedulers that spawn new processes (losing all conversation
context), frost-scheduler injects prompts into your existing session.

Usage:
  python frost-scheduler.py              # Start daemon
  python frost-scheduler.py --once       # Check once and exit (testing)
  python frost-scheduler.py --list       # Show all tasks and status
  python frost-scheduler.py --validate   # Validate schedule config
  python frost-scheduler.py --version    # Show version

Environment variables:
  FROST_SCHEDULER_CONFIG  — Path to config directory (default: ~/.frost-scheduler/)
  FROST_SCHEDULER_WAKE    — Wake method: sendinput | claude-cli | command (default: auto-detect)

Requires: Python 3.8+
Optional: pywin32 (Windows SendInput wake method)
"""

__version__ = "1.0.0"

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# === CONFIGURATION ===
DEFAULT_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".frost-scheduler")
CONFIG_DIR = os.environ.get("FROST_SCHEDULER_CONFIG", DEFAULT_CONFIG_DIR)

SCHEDULE_FILE = os.path.join(CONFIG_DIR, "schedule.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")
PENDING_FILE = os.path.join(CONFIG_DIR, "pending.json")
ACK_DIR = os.path.join(CONFIG_DIR, "ack")
LOG_FILE = os.path.join(CONFIG_DIR, "frost-scheduler.log")
HEARTBEAT_FILE = os.path.join(CONFIG_DIR, "heartbeat.json")
PID_FILE = os.path.join(CONFIG_DIR, "frost-scheduler.pid")

POLL_INTERVAL = 30  # seconds
PYTHON_EXE = sys.executable

# Ensure config directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(ACK_DIR, exist_ok=True)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# === LOGGING ===
def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============================================================
# WAKE BACKENDS — pluggable methods to wake a Claude session
# ============================================================

class WakeBackend:
    """Base class for wake methods."""
    name = "base"

    def wake(self, trigger_text):
        """Send trigger_text to the AI session. Returns True on success."""
        raise NotImplementedError

    @staticmethod
    def available():
        """Return True if this backend can run on the current platform."""
        return False


class SendInputWake(WakeBackend):
    """Windows-only: type text into a terminal window via Win32 SendInput."""
    name = "sendinput"

    def __init__(self, window_title="claude"):
        self.window_title = window_title
        self._setup_win32()

    def _setup_win32(self):
        import ctypes
        import ctypes.wintypes
        self.ctypes = ctypes
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

        # Input structures
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_UNICODE = 0x0004
        VK_RETURN = 0x0D
        SW_RESTORE = 9

        self.INPUT_KEYBOARD = INPUT_KEYBOARD
        self.KEYEVENTF_KEYUP = KEYEVENTF_KEYUP
        self.KEYEVENTF_UNICODE = KEYEVENTF_UNICODE
        self.VK_RETURN = VK_RETURN
        self.SW_RESTORE = SW_RESTORE

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]
        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort), ("wParamH", ctypes.c_ushort)]
        class INPUT_UNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]
        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", ctypes.c_ulong), ("u", INPUT_UNION)]

        self.INPUT = INPUT
        self.user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
        self.user32.SendInput.restype = ctypes.c_uint

    def _find_window(self):
        result = []
        ctypes = self.ctypes
        def callback(hwnd, _):
            if self.user32.IsWindowVisible(hwnd):
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buf, length + 1)
                    if self.window_title.lower() in buf.value.lower():
                        result.append((hwnd, buf.value))
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        self.user32.EnumWindows(WNDENUMPROC(callback), 0)
        return result

    def _activate_window(self, hwnd):
        self.user32.keybd_event(0x12, 0, 0, 0)
        self.user32.keybd_event(0x12, 0, 2, 0)
        time.sleep(0.05)
        self.user32.ShowWindow(hwnd, self.SW_RESTORE)
        self.user32.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return self.user32.GetForegroundWindow() == hwnd

    def _send_text(self, text):
        sent = 0
        for ch in text:
            inputs = (self.INPUT * 2)()
            inputs[0].type = self.INPUT_KEYBOARD
            inputs[0].ki.wScan = ord(ch)
            inputs[0].ki.dwFlags = self.KEYEVENTF_UNICODE
            inputs[1].type = self.INPUT_KEYBOARD
            inputs[1].ki.wScan = ord(ch)
            inputs[1].ki.dwFlags = self.KEYEVENTF_UNICODE | self.KEYEVENTF_KEYUP
            n = self.user32.SendInput(2, inputs, self.ctypes.sizeof(self.INPUT))
            sent += n
            time.sleep(0.003)
        return sent

    def _send_enter(self):
        inputs = (self.INPUT * 2)()
        inputs[0].type = self.INPUT_KEYBOARD
        inputs[0].ki.wVk = self.VK_RETURN
        inputs[1].type = self.INPUT_KEYBOARD
        inputs[1].ki.wVk = self.VK_RETURN
        inputs[1].ki.dwFlags = self.KEYEVENTF_KEYUP
        return self.user32.SendInput(2, inputs, self.ctypes.sizeof(self.INPUT))

    def wake(self, trigger_text):
        windows = self._find_window()
        if not windows:
            log(f"[sendinput] Window '{self.window_title}' not found")
            return False

        hwnd, title = windows[0]
        for attempt in range(3):
            self._activate_window(hwnd)
            time.sleep(0.8)
            fg = self.user32.GetForegroundWindow()
            if fg != hwnd:
                log(f"[sendinput] Attempt {attempt+1}/3: wrong foreground window")
                time.sleep(1.0)
                continue

            self._send_text(trigger_text)
            time.sleep(1.5)
            self._send_enter()
            time.sleep(0.3)
            self._send_enter()  # safety double-enter
            log(f"[sendinput] Sent: {trigger_text[:60]}...")
            return True

        log(f"[sendinput] All 3 attempts failed")
        return False

    @staticmethod
    def available():
        return sys.platform == "win32"


class ClaudeCliWake(WakeBackend):
    """Cross-platform: use `claude -p` to send a prompt (spawns new context)."""
    name = "claude-cli"

    def __init__(self, claude_cmd="claude"):
        self.claude_cmd = claude_cmd

    def wake(self, trigger_text):
        try:
            proc = subprocess.run(
                [self.claude_cmd, "-p", trigger_text],
                capture_output=True, text=True, timeout=300,
            )
            log(f"[claude-cli] exit={proc.returncode}")
            return proc.returncode == 0
        except FileNotFoundError:
            log(f"[claude-cli] '{self.claude_cmd}' not found in PATH")
            return False
        except subprocess.TimeoutExpired:
            log(f"[claude-cli] Timeout (300s)")
            return False
        except Exception as e:
            log(f"[claude-cli] Error: {e}")
            return False

    @staticmethod
    def available():
        try:
            subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False


class CommandWake(WakeBackend):
    """Run an arbitrary shell command, with {MESSAGE} placeholder."""
    name = "command"

    def __init__(self, command_template):
        self.command_template = command_template

    def wake(self, trigger_text):
        cmd = self.command_template.replace("{MESSAGE}", trigger_text)
        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120,
            )
            log(f"[command] exit={proc.returncode}")
            return proc.returncode == 0
        except Exception as e:
            log(f"[command] Error: {e}")
            return False

    @staticmethod
    def available():
        return True


class PendingOnlyWake(WakeBackend):
    """No-op wake: just queue to pending.json, external process polls it."""
    name = "pending-only"

    def wake(self, trigger_text):
        log(f"[pending-only] Task queued (no active wake)")
        return True

    @staticmethod
    def available():
        return True


def create_wake_backend(config):
    """Create wake backend from config. Auto-detects if not specified."""
    wake_cfg = config.get("wake", {})
    method = os.environ.get("FROST_SCHEDULER_WAKE", wake_cfg.get("method", "auto"))

    if method == "sendinput":
        window = wake_cfg.get("window_title", "claude")
        return SendInputWake(window_title=window)
    elif method == "claude-cli":
        cmd = wake_cfg.get("claude_command", "claude")
        return ClaudeCliWake(claude_cmd=cmd)
    elif method == "command":
        template = wake_cfg.get("command_template", "")
        if not template:
            log("WARNING: wake method 'command' but no command_template specified")
            return PendingOnlyWake()
        return CommandWake(command_template=template)
    elif method == "pending-only":
        return PendingOnlyWake()
    elif method == "auto":
        # Auto-detect: Windows → sendinput, else → pending-only
        if SendInputWake.available():
            window = wake_cfg.get("window_title", "claude")
            return SendInputWake(window_title=window)
        else:
            return PendingOnlyWake()
    else:
        log(f"WARNING: Unknown wake method '{method}', falling back to pending-only")
        return PendingOnlyWake()


# === STATE MANAGEMENT ===
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


# === SCHEDULE LOADING (with hot-reload) ===
_cached_schedule = None
_cached_mtime = 0


def load_schedule():
    global _cached_schedule, _cached_mtime
    try:
        mtime = os.path.getmtime(SCHEDULE_FILE)
        if mtime != _cached_mtime or _cached_schedule is None:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                _cached_schedule = json.load(f)
            _cached_mtime = mtime
            log(f"Schedule loaded ({len(_cached_schedule.get('tasks', []))} tasks)")
    except Exception as e:
        log(f"Failed to load schedule: {e}")
        if _cached_schedule is None:
            _cached_schedule = {"tasks": []}
    return _cached_schedule


# === SCHEDULE EVALUATION ===
DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def parse_time(time_str):
    """Parse 'HH:MM' to (hour, minute)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def in_active_window(schedule, now):
    """Check if current time is within start_after..stop_before window."""
    start = schedule.get("start_after")
    stop = schedule.get("stop_before")
    if start:
        sh, sm = parse_time(start)
        if now.hour < sh or (now.hour == sh and now.minute < sm):
            return False
    if stop:
        eh, em = parse_time(stop)
        if now.hour > eh or (now.hour == eh and now.minute > em):
            return False
    return True


def is_task_due(task, state, now):
    """Determine if a task should fire right now."""
    if not task.get("enabled", True):
        return False

    task_id = task["id"]
    task_state = state.get("tasks", {}).get(task_id, {})
    last_run_str = task_state.get("last_run")
    schedule = task.get("schedule", {})
    stype = schedule.get("type")
    if not stype:
        return False

    # start_date: don't fire before this date
    start_date_str = schedule.get("start_date")
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        if now.date() < start_date:
            return False

    # once: fire only once ever
    if schedule.get("once") and last_run_str:
        return False

    if stype == "daily":
        h, m = parse_time(schedule["time"])
        today_target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < today_target:
            return False
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            if last_run.date() == now.date():
                return False
        return True

    elif stype == "interval":
        hours = schedule.get("hours", 0)
        minutes = schedule.get("minutes", 0)
        interval_sec = hours * 3600 + minutes * 60

        # Night mode: use longer interval during night hours
        night_cfg = schedule.get("night_hours")
        if night_cfg and schedule.get("night_interval_hours"):
            nh_start = parse_time(night_cfg[0])
            nh_end = parse_time(night_cfg[1])
            cur = (now.hour, now.minute)
            if nh_start > nh_end:
                is_night = cur >= nh_start or cur < nh_end
            else:
                is_night = nh_start <= cur < nh_end
            if is_night:
                interval_sec = schedule["night_interval_hours"] * 3600

        if interval_sec <= 0:
            return False
        if not in_active_window(schedule, now):
            return False
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            elapsed = (now - last_run).total_seconds()
            return elapsed >= interval_sec
        return True

    elif stype == "weekly":
        target_day = DAY_MAP.get(schedule.get("day", "").lower())
        if target_day is None:
            return False
        if now.weekday() != target_day:
            return False
        h, m = parse_time(schedule["time"])
        today_target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < today_target:
            return False
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            if (now - last_run).days < 1:
                return False
        return True

    elif stype == "monthly":
        target_dom = schedule.get("day_of_month", 1)
        if now.day != target_dom:
            return False
        h, m = parse_time(schedule["time"])
        today_target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < today_target:
            return False
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            if last_run.month == now.month and last_run.year == now.year:
                return False
        return True

    return False


# === TASK EXECUTION ===
def run_script(task):
    """Run a script or shell command silently."""
    script = task.get("script")
    script_shell = task.get("script_shell")
    args = task.get("script_args", [])

    try:
        if script:
            if not os.path.isabs(script):
                # Look relative to schedule file dir, then cwd
                sched_dir = os.path.dirname(SCHEDULE_FILE)
                candidate = os.path.join(sched_dir, script)
                if os.path.exists(candidate):
                    script = candidate
            cmd = [PYTHON_EXE, script] + args
        elif script_shell:
            home = os.path.expanduser("~")
            if isinstance(script_shell, str):
                script_shell = script_shell.replace("{HOME}", home)
            cmd = script_shell
        else:
            return {"success": False, "error": "no script defined"}

        kwargs = dict(
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        if isinstance(cmd, str):
            kwargs["shell"] = True

        proc = subprocess.run(cmd, **kwargs)
        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout[-200:] if proc.stdout else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout (120s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def queue_ai_task(task_id, command):
    """Append an AI task to pending queue. Returns (success, already_had_items)."""
    try:
        queue = []
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                queue = json.load(f)
        already_had = len(queue) > 0
        queue.append({
            "task_id": task_id,
            "command": command,
            "queued_at": datetime.now().isoformat(),
        })
        tmp = PENDING_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        os.replace(tmp, PENDING_FILE)
        return True, already_had
    except Exception as e:
        log(f"  Failed to write pending queue: {e}")
        return False, False


def write_ack_pending(task_id):
    """Write .pending marker for ack tracking."""
    try:
        path = os.path.join(ACK_DIR, f"{task_id}.pending")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"time": datetime.now().isoformat(), "task": task_id}, f)
    except Exception as e:
        log(f"  Failed to write ack pending: {e}")


def execute_task(task, wake_backend, trigger_text):
    """Execute a task: run script and/or queue AI command + wake."""
    result = {"started": datetime.now().isoformat()}

    # Phase 1: Run script (silent)
    if task.get("script") or task.get("script_shell"):
        script_result = run_script(task)
        result["script"] = script_result
        log(f"  Script: exit={script_result.get('exit_code', '?')} success={script_result.get('success')}")

    # Phase 2: AI command — queue + wake
    if task.get("command"):
        write_ack_pending(task["id"])
        queued, already_had = queue_ai_task(task["id"], task["command"])

        if queued:
            log(f"  Queued: {task['id']} ({len(task['command'])} chars)")
            if already_had:
                # Check if queue is stale (>5 min) before re-triggering
                stale = False
                try:
                    with open(PENDING_FILE, "r", encoding="utf-8") as f:
                        q = json.load(f)
                    if q and q[0].get("queued_at"):
                        age = (datetime.now() - datetime.fromisoformat(q[0]["queued_at"])).total_seconds()
                        stale = age > 300
                except Exception:
                    pass
                if stale:
                    log(f"  Queue stale (>5min), re-triggering wake")
                    result["send_success"] = wake_backend.wake(trigger_text)
                else:
                    log(f"  Skipped duplicate wake (queue not stale)")
                    result["send_success"] = True
            else:
                result["send_success"] = wake_backend.wake(trigger_text)
        else:
            result["send_success"] = False

    # Phase 3: Post-command (delayed follow-up)
    if task.get("post_command") and result.get("send_success"):
        delay = task.get("post_delay", 60)
        log(f"  Waiting {delay}s for post-command...")
        time.sleep(delay)
        post_ok = wake_backend.wake(task["post_command"])
        result["post_sent"] = post_ok

    result["finished"] = datetime.now().isoformat()
    result["success"] = True
    if task.get("command") and not result.get("send_success"):
        result["success"] = False
    if (task.get("script") or task.get("script_shell")) and not result.get("script", {}).get("success"):
        result["success"] = False

    return result


# === LIST COMMAND ===
def list_tasks():
    """Print all tasks and their status."""
    schedule = load_schedule()
    state = load_state()
    now = datetime.now()

    print(f"\n{'ID':<30} {'On':>3} {'Type':<8} {'Schedule':<25} {'Last Run':<20} {'Description'}")
    print("-" * 120)

    for task in schedule.get("tasks", []):
        tid = task["id"]
        enabled = "Y" if task.get("enabled", True) else "N"
        ttype = "AI" if task.get("command") else "Script"
        sched = task["schedule"]
        sched_str = f"{sched['type']}"
        if sched.get("time"):
            sched_str += f" {sched['time']}"
        if sched.get("hours"):
            sched_str += f" every {sched['hours']}h"
        if sched.get("minutes"):
            sched_str += f" every {sched['minutes']}m"
        if sched.get("day"):
            sched_str += f" {sched['day']}"

        ts = state.get("tasks", {}).get(tid, {})
        last = ts.get("last_run", "-")[:19] if ts.get("last_run") else "-"
        desc = task.get("description", "")

        due = "*" if is_task_due(task, state, now) else " "
        print(f"{due}{tid:<29} {enabled:>3} {ttype:<8} {sched_str:<25} {last:<20} {desc}")

    print(f"\n* = due now")


# === VALIDATE ===
def validate_schedule():
    """Validate the schedule config file."""
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Schedule file not found: {SCHEDULE_FILE}")
        return False
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        return False

    tasks = data.get("tasks", [])
    errors = []
    ids_seen = set()
    for i, task in enumerate(tasks):
        tid = task.get("id")
        if not tid:
            errors.append(f"Task {i}: missing 'id'")
            continue
        if tid in ids_seen:
            errors.append(f"Task '{tid}': duplicate id")
        ids_seen.add(tid)

        sched = task.get("schedule", {})
        stype = sched.get("type")
        if stype not in ("daily", "interval", "weekly", "monthly"):
            errors.append(f"Task '{tid}': unknown schedule type '{stype}'")
        if stype in ("daily", "weekly", "monthly") and not sched.get("time"):
            errors.append(f"Task '{tid}': {stype} schedule requires 'time'")
        if stype == "weekly" and not sched.get("day"):
            errors.append(f"Task '{tid}': weekly schedule requires 'day'")
        if stype == "interval" and not (sched.get("hours") or sched.get("minutes")):
            errors.append(f"Task '{tid}': interval requires 'hours' or 'minutes'")

        if not task.get("command") and not task.get("script") and not task.get("script_shell"):
            errors.append(f"Task '{tid}': no command, script, or script_shell defined")

    if errors:
        print(f"Validation failed ({len(errors)} errors):")
        for err in errors:
            print(f"  - {err}")
        return False

    print(f"OK: {len(tasks)} tasks validated")
    return True


# === HEARTBEAT / PID ===
_daemon_started = None


def write_heartbeat():
    try:
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "pid": os.getpid(),
                "timestamp": datetime.now().isoformat(),
                "started": _daemon_started or datetime.now().isoformat(),
            }, f)
    except Exception:
        pass


def write_pid():
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def cleanup_pid():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


# === SINGLETON (cross-platform) ===
_lock_file_handle = None


def acquire_singleton():
    """Ensure only one daemon instance. Uses PID file + process check."""
    global _lock_file_handle
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            # Check if process is alive
            if sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x0400, False, old_pid)  # PROCESS_QUERY_INFORMATION
                if handle:
                    kernel32.CloseHandle(handle)
                    return False  # Process exists
            else:
                os.kill(old_pid, 0)  # Signal 0 = check existence
                return False  # Process exists
        except (ValueError, OSError, PermissionError):
            pass  # Stale PID file, proceed

    write_pid()
    return True


# === SIGNAL HANDLING ===
_shutdown_requested = False


def handle_signal(signum, frame):
    global _shutdown_requested
    log(f"Signal {signum} received, shutting down gracefully...")
    _shutdown_requested = True


# === MAIN ===
def main(once=False):
    global _shutdown_requested, _daemon_started

    if not once and not acquire_singleton():
        log("Another frost-scheduler daemon is already running")
        print("ERROR: Another frost-scheduler daemon is already running", file=sys.stderr)
        sys.exit(1)

    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, handle_signal)
    except Exception as e:
        log(f"Signal handler registration failed: {e}")

    _daemon_started = datetime.now().isoformat()

    log("=" * 50)
    log(f"frost-scheduler v{__version__} starting")
    log(f"Config dir:  {CONFIG_DIR}")
    log(f"Schedule:    {SCHEDULE_FILE}")
    log(f"Poll:        {POLL_INTERVAL}s")
    log(f"PID:         {os.getpid()}")

    # Load config for wake backend
    schedule_data = load_schedule()
    wake_backend = create_wake_backend(schedule_data)
    trigger_text = schedule_data.get("trigger_text", "check schedule")
    log(f"Wake method: {wake_backend.name}")
    log("=" * 50)

    write_pid()
    write_heartbeat()

    state = load_state()
    state["daemon_started"] = _daemon_started
    save_state(state)

    try:
        while not _shutdown_requested:
            try:
                now = datetime.now()
                schedule_data = load_schedule()
                write_heartbeat()

                # Update wake backend if config changed
                new_backend = create_wake_backend(schedule_data)
                if new_backend.name != wake_backend.name:
                    log(f"Wake method changed: {wake_backend.name} -> {new_backend.name}")
                    wake_backend = new_backend
                trigger_text = schedule_data.get("trigger_text", "check schedule")

                due_tasks = [t for t in schedule_data.get("tasks", []) if is_task_due(t, state, now)]

                for task in due_tasks:
                    if _shutdown_requested:
                        break
                    tid = task["id"]
                    log(f"Executing: {tid} ({task.get('description', '')})")
                    result = execute_task(task, wake_backend, trigger_text)

                    state.setdefault("tasks", {})[tid] = {
                        "last_run": now.isoformat(),
                        "last_success": result.get("success", False),
                        "run_count": state.get("tasks", {}).get(tid, {}).get("run_count", 0) + 1,
                        "fail_count": 0 if result.get("success") else state.get("tasks", {}).get(tid, {}).get("fail_count", 0) + 1,
                    }
                    save_state(state)

                    if task.get("command") and len(due_tasks) > 1:
                        time.sleep(3)

            except Exception as e:
                log(f"Main loop error: {e}")

            if once:
                log("--once mode, exiting")
                break

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log("KeyboardInterrupt, shutting down...")
    finally:
        log("frost-scheduler daemon stopped")
        cleanup_pid()


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_tasks()
    elif "--once" in sys.argv:
        main(once=True)
    elif "--validate" in sys.argv:
        sys.exit(0 if validate_schedule() else 1)
    elif "--version" in sys.argv:
        print(f"frost-scheduler v{__version__}")
    else:
        main()
