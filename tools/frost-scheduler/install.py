#!/usr/bin/env python3
"""
install.py — One-click setup for frost-scheduler

Creates config directory, copies example schedule, and optionally
sets up auto-start (Windows Task Scheduler / systemd / launchd).

Usage:
  python install.py                    # Interactive setup
  python install.py --config-only      # Just create config dir + example
  python install.py --autostart        # Also register auto-start
  python install.py --uninstall        # Remove auto-start (keeps config)
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".frost-scheduler")
TASK_NAME = "FrostScheduler"


def setup_config(config_dir):
    """Create config directory and copy example schedule."""
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(os.path.join(config_dir, "ack"), exist_ok=True)

    schedule_path = os.path.join(config_dir, "schedule.json")
    example_path = os.path.join(TOOL_DIR, "schedule.example.json")

    if os.path.exists(schedule_path):
        print(f"  Schedule already exists: {schedule_path}")
        print(f"  (Example at: {example_path})")
    else:
        shutil.copy2(example_path, schedule_path)
        print(f"  Created: {schedule_path}")

    # Copy tools
    for script in ["frost-scheduler.py", "frost-ack.py"]:
        src = os.path.join(TOOL_DIR, script)
        dst = os.path.join(config_dir, script)
        shutil.copy2(src, dst)
        print(f"  Installed: {dst}")

    print(f"\n  Config directory: {config_dir}")
    return config_dir


def setup_autostart_windows(config_dir):
    """Register with Windows Task Scheduler."""
    python = sys.executable
    script = os.path.join(config_dir, "frost-scheduler.py")

    # Create XML task definition
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Frost Scheduler - AI task scheduler daemon</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python}</Command>
      <Arguments>"{script}"</Arguments>
      <WorkingDirectory>{config_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    xml_path = os.path.join(config_dir, "task-scheduler.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(xml)

    try:
        subprocess.run(
            ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", xml_path, "/F"],
            check=True, capture_output=True, text=True,
        )
        print(f"  Registered Windows Task: {TASK_NAME}")
        print(f"  Starts on login. Run manually: schtasks /Run /TN {TASK_NAME}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Failed to register task (run as admin?): {e.stderr}")
        return False


def setup_autostart_systemd(config_dir):
    """Create a systemd user service."""
    python = sys.executable
    script = os.path.join(config_dir, "frost-scheduler.py")
    service_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(service_dir, exist_ok=True)

    unit = f"""[Unit]
Description=Frost Scheduler - AI task scheduler daemon
After=network.target

[Service]
Type=simple
ExecStart={python} {script}
WorkingDirectory={config_dir}
Restart=on-failure
RestartSec=10
Environment=FROST_SCHEDULER_CONFIG={config_dir}

[Install]
WantedBy=default.target
"""
    unit_path = os.path.join(service_dir, "frost-scheduler.service")
    with open(unit_path, "w") as f:
        f.write(unit)

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
        subprocess.run(["systemctl", "--user", "enable", "frost-scheduler"], check=True, capture_output=True)
        print(f"  Created: {unit_path}")
        print(f"  Start:   systemctl --user start frost-scheduler")
        print(f"  Status:  systemctl --user status frost-scheduler")
        return True
    except Exception as e:
        print(f"  Created unit file but failed to enable: {e}")
        print(f"  Manual: systemctl --user enable --now frost-scheduler")
        return False


def setup_autostart_launchd(config_dir):
    """Create a macOS launchd plist."""
    python = sys.executable
    script = os.path.join(config_dir, "frost-scheduler.py")
    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(plist_dir, exist_ok=True)

    label = "com.permafrost.frost-scheduler"
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{script}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{config_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>FROST_SCHEDULER_CONFIG</key>
        <string>{config_dir}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>{config_dir}/frost-scheduler-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{config_dir}/frost-scheduler-stderr.log</string>
</dict>
</plist>"""

    plist_path = os.path.join(plist_dir, f"{label}.plist")
    with open(plist_path, "w") as f:
        f.write(plist)

    print(f"  Created: {plist_path}")
    print(f"  Load:    launchctl load {plist_path}")
    print(f"  Status:  launchctl list | grep frost-scheduler")
    return True


def uninstall_autostart():
    """Remove auto-start registration."""
    system = platform.system()
    if system == "Windows":
        try:
            subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                          check=True, capture_output=True, text=True)
            print(f"  Removed Windows Task: {TASK_NAME}")
        except subprocess.CalledProcessError:
            print(f"  Task '{TASK_NAME}' not found or already removed")
    elif system == "Linux":
        try:
            subprocess.run(["systemctl", "--user", "disable", "--now", "frost-scheduler"],
                          capture_output=True)
            unit = os.path.expanduser("~/.config/systemd/user/frost-scheduler.service")
            if os.path.exists(unit):
                os.remove(unit)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            print("  Removed systemd service")
        except Exception as e:
            print(f"  Removal failed: {e}")
    elif system == "Darwin":
        label = "com.permafrost.frost-scheduler"
        plist = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        try:
            subprocess.run(["launchctl", "unload", plist], capture_output=True)
        except Exception:
            pass
        if os.path.exists(plist):
            os.remove(plist)
            print("  Removed launchd agent")
        else:
            print("  No launchd agent found")


def main():
    print("=" * 50)
    print("frost-scheduler installer")
    print("=" * 50)

    config_dir = DEFAULT_CONFIG_DIR

    if "--uninstall" in sys.argv:
        print("\nRemoving auto-start...")
        uninstall_autostart()
        print("\nDone. Config files in {config_dir} were NOT removed.")
        return

    print(f"\n1. Setting up config directory...")
    setup_config(config_dir)

    if "--config-only" in sys.argv:
        print("\nDone (config only).")
        print(f"\nTo start manually:")
        print(f"  python {os.path.join(config_dir, 'frost-scheduler.py')}")
        return

    if "--autostart" in sys.argv:
        print(f"\n2. Setting up auto-start...")
        system = platform.system()
        if system == "Windows":
            setup_autostart_windows(config_dir)
        elif system == "Linux":
            setup_autostart_systemd(config_dir)
        elif system == "Darwin":
            setup_autostart_launchd(config_dir)
        else:
            print(f"  Auto-start not supported on {system}")
            print(f"  Add to your startup: python {os.path.join(config_dir, 'frost-scheduler.py')}")

    print("\n" + "=" * 50)
    print("Setup complete!")
    print(f"\nEdit your schedule:  {os.path.join(config_dir, 'schedule.json')}")
    print(f"Start daemon:        python {os.path.join(config_dir, 'frost-scheduler.py')}")
    print(f"Check tasks:         python {os.path.join(config_dir, 'frost-scheduler.py')} --list")
    print(f"Ack a task:          python {os.path.join(config_dir, 'frost-ack.py')} ack <task-id>")


if __name__ == "__main__":
    main()
