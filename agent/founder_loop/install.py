"""
Auto-start-on-login installer for the founder_loop daemon.

Generates a platform-appropriate user-level service unit that runs
``neuro-os start`` whenever the user logs in. Three platforms:

* **macOS** — ``~/Library/LaunchAgents/com.founderloop.daemon.plist``
  loaded with ``launchctl``.
* **Linux (systemd-user)** —
  ``~/.config/systemd/user/founder-loop.service`` enabled with
  ``systemctl --user enable --now founder-loop.service``.
* **Windows** — Task Scheduler XML imported with ``schtasks /create``.

All three run as the user, not root. None of them open ports
externally. The daemon refuses non-loopback binds at the API level
regardless.

Usage::

    neuro-os autostart install   # writes the unit and enables it
    neuro-os autostart status    # is it installed / running?
    neuro-os autostart uninstall # removes the unit

``--dry-run`` on any of these prints what would be done and exits.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, Tuple


Platform = Literal["macos", "linux", "windows", "unknown"]


def detect_platform() -> Platform:
    s = platform.system().lower()
    if s == "darwin":
        return "macos"
    if s == "linux":
        return "linux"
    if s == "windows":
        return "windows"
    return "unknown"


def neuro_os_path() -> str:
    """Return absolute path to the ``neuro-os`` executable, or fall
    back to ``python -m agent`` if the entry point isn't on PATH."""
    found = shutil.which("neuro-os")
    if found:
        return found
    # Fall back to the running interpreter + module form.
    return f"{sys.executable} -m agent"


# ---------------------------------------------------------------------------
# Unit content generators
# ---------------------------------------------------------------------------


@dataclass
class _Plan:
    """What ``install`` would do. Returned in --dry-run mode."""
    platform: Platform
    unit_path: Path
    unit_content: str
    enable_cmd: List[str]
    disable_cmd: List[str]


def plan(platform_name: Optional[Platform] = None) -> _Plan:
    p = platform_name or detect_platform()
    bin_str = neuro_os_path()
    if p == "macos":
        return _macos_plan(bin_str)
    if p == "linux":
        return _linux_plan(bin_str)
    if p == "windows":
        return _windows_plan(bin_str)
    raise RuntimeError(f"unsupported platform: {platform.system()!r}")


def _macos_plan(bin_str: str) -> _Plan:
    label = "com.founderloop.daemon"
    home = Path.home()
    unit_path = home / "Library" / "LaunchAgents" / f"{label}.plist"
    log_path = home / ".founder_loop" / "daemon.log"
    # Args: split on spaces in case bin_str is "python -m agent"
    args_xml = "\n".join(
        f"    <string>{x}</string>" for x in (bin_str.split() + ["start", "--no-open"])
    )
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{args_xml}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log_path}</string>
  <key>StandardErrorPath</key>
  <string>{log_path}</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
"""
    return _Plan(
        platform="macos",
        unit_path=unit_path,
        unit_content=content,
        enable_cmd=["launchctl", "load", "-w", str(unit_path)],
        disable_cmd=["launchctl", "unload", "-w", str(unit_path)],
    )


def _linux_plan(bin_str: str) -> _Plan:
    home = Path.home()
    unit_path = home / ".config" / "systemd" / "user" / "founder-loop.service"
    exec_start = bin_str + " start --no-open"
    content = f"""[Unit]
Description=Founder Loop daemon — daily contract + sublimation
After=default.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
StandardOutput=append:%h/.founder_loop/daemon.log
StandardError=append:%h/.founder_loop/daemon.log

[Install]
WantedBy=default.target
"""
    return _Plan(
        platform="linux",
        unit_path=unit_path,
        unit_content=content,
        enable_cmd=[
            "systemctl", "--user", "daemon-reload",
        ],
        # Caller appends the actual enable below; we model the reload as
        # the primary "make systemd see this" command.
        disable_cmd=[
            "systemctl", "--user", "disable", "--now", "founder-loop.service",
        ],
    )


def _windows_plan(bin_str: str) -> _Plan:
    home = Path.home()
    unit_path = home / "AppData" / "Local" / "FounderLoop" / "autostart.xml"
    # Task Scheduler XML for a per-user task that runs at logon.
    # We use the bin path as the Command and " start --no-open" as Args.
    parts = bin_str.split()
    cmd = parts[0]
    args = " ".join(parts[1:] + ["start", "--no-open"])
    content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Founder Loop daemon — daily contract + sublimation</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>{cmd}</Command>
      <Arguments>{args}</Arguments>
    </Exec>
  </Actions>
</Task>
"""
    return _Plan(
        platform="windows",
        unit_path=unit_path,
        unit_content=content,
        enable_cmd=[
            "schtasks", "/Create", "/F", "/TN", "FounderLoop",
            "/XML", str(unit_path),
        ],
        disable_cmd=[
            "schtasks", "/Delete", "/F", "/TN", "FounderLoop",
        ],
    )


# ---------------------------------------------------------------------------
# Action functions
# ---------------------------------------------------------------------------


def install(*, dry_run: bool = False) -> Tuple[bool, str]:
    p = plan()
    if dry_run:
        return True, _dry_run_summary("install", p)
    p.unit_path.parent.mkdir(parents=True, exist_ok=True)
    p.unit_path.write_text(p.unit_content, encoding="utf-8")
    log_dir = Path.home() / ".founder_loop"
    log_dir.mkdir(parents=True, exist_ok=True)

    msgs = [f"Wrote unit: {p.unit_path}"]

    # Run the enable command (best-effort; errors return False but we
    # still leave the unit on disk so the user can recover).
    try:
        result = subprocess.run(
            p.enable_cmd, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            msgs.append(
                f"Warning: {' '.join(p.enable_cmd)} exited with "
                f"{result.returncode}: {result.stderr.strip()}"
            )
        else:
            msgs.append(f"Ran: {' '.join(p.enable_cmd)}")
    except FileNotFoundError:
        msgs.append(
            f"Warning: '{p.enable_cmd[0]}' not on PATH — unit written but "
            "not enabled. Enable it manually."
        )

    # Linux extra step: enable the service after the daemon-reload.
    if p.platform == "linux":
        try:
            r = subprocess.run(
                ["systemctl", "--user", "enable", "--now", "founder-loop.service"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                msgs.append(f"Warning: systemctl enable failed: {r.stderr.strip()}")
            else:
                msgs.append("Ran: systemctl --user enable --now founder-loop.service")
        except FileNotFoundError:
            msgs.append("Warning: systemctl not found")

    return True, "\n".join(msgs)


def uninstall(*, dry_run: bool = False) -> Tuple[bool, str]:
    p = plan()
    if dry_run:
        return True, _dry_run_summary("uninstall", p)
    msgs = []
    try:
        result = subprocess.run(
            p.disable_cmd, capture_output=True, text=True, timeout=15,
        )
        msgs.append(
            f"Ran: {' '.join(p.disable_cmd)} → exit {result.returncode}"
        )
    except FileNotFoundError:
        msgs.append(f"Warning: {p.disable_cmd[0]!r} not on PATH")
    if p.unit_path.exists():
        p.unit_path.unlink()
        msgs.append(f"Removed unit: {p.unit_path}")
    else:
        msgs.append(f"Unit already absent: {p.unit_path}")
    return True, "\n".join(msgs)


def status() -> Tuple[bool, str]:
    p = plan()
    parts = [f"Platform: {p.platform}", f"Unit path: {p.unit_path}"]
    parts.append("Installed: " + ("yes" if p.unit_path.exists() else "no"))
    if p.platform == "linux":
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-active", "founder-loop.service"],
                capture_output=True, text=True, timeout=5,
            )
            parts.append(f"systemd active: {r.stdout.strip() or r.returncode}")
        except FileNotFoundError:
            parts.append("systemd: not available")
    elif p.platform == "macos":
        try:
            r = subprocess.run(
                ["launchctl", "list", "com.founderloop.daemon"],
                capture_output=True, text=True, timeout=5,
            )
            parts.append(
                "launchd loaded: " + ("yes" if r.returncode == 0 else "no")
            )
        except FileNotFoundError:
            parts.append("launchctl: not available")
    elif p.platform == "windows":
        try:
            r = subprocess.run(
                ["schtasks", "/Query", "/TN", "FounderLoop"],
                capture_output=True, text=True, timeout=5,
            )
            parts.append(
                "Task Scheduler: " + ("present" if r.returncode == 0 else "absent")
            )
        except FileNotFoundError:
            parts.append("schtasks: not available")
    return True, "\n".join(parts)


def _dry_run_summary(verb: str, p: _Plan) -> str:
    lines = [
        f"-- DRY RUN ({verb}, platform={p.platform}) --",
        f"Would write unit: {p.unit_path}",
        "Would run:",
        f"  {' '.join(p.enable_cmd) if verb == 'install' else ' '.join(p.disable_cmd)}",
        "",
        "Unit content:",
        "─" * 60,
        p.unit_content,
    ]
    return "\n".join(lines)


__all__ = [
    "detect_platform",
    "plan",
    "install",
    "uninstall",
    "status",
]
