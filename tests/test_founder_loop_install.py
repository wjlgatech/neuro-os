"""Tests for the autostart installer (``agent.founder_loop.install``).

We don't actually install anything — we exercise the planning function
which is the only side-effect-free surface and validate that the
generated unit content is well-formed for each platform.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET


from agent.founder_loop.install import (
    detect_platform,
    plan,
)


def test_detect_platform_returns_known_value():
    p = detect_platform()
    assert p in ("macos", "linux", "windows", "unknown")


def test_macos_plan_is_valid_plist():
    p = plan(platform_name="macos")
    assert p.platform == "macos"
    assert str(p.unit_path).endswith(".plist")
    assert "<key>Label</key>" in p.unit_content
    assert "<key>RunAtLoad</key>" in p.unit_content
    assert "<true/>" in p.unit_content
    # XML well-formed
    ET.fromstring(p.unit_content)
    # Enable command uses launchctl
    assert p.enable_cmd[0] == "launchctl"
    assert p.disable_cmd[0] == "launchctl"


def test_linux_plan_is_valid_systemd_unit():
    p = plan(platform_name="linux")
    assert p.platform == "linux"
    assert str(p.unit_path).endswith("founder-loop.service")
    # Sections
    assert "[Unit]" in p.unit_content
    assert "[Service]" in p.unit_content
    assert "[Install]" in p.unit_content
    assert "ExecStart=" in p.unit_content
    assert "Restart=on-failure" in p.unit_content
    assert "WantedBy=default.target" in p.unit_content


def test_windows_plan_is_valid_task_scheduler_xml():
    p = plan(platform_name="windows")
    assert p.platform == "windows"
    assert str(p.unit_path).endswith("autostart.xml")
    # XML well-formed (the namespace makes parsing non-trivial; we
    # validate by stripping the ns prefix and checking root element).
    root = ET.fromstring(p.unit_content)
    assert root.tag.endswith("Task")
    # Triggers / Actions sections present
    assert "<LogonTrigger>" in p.unit_content
    assert "<Exec>" in p.unit_content


def test_dry_run_summary_renders_unit_content():
    """``install(dry_run=True)`` must echo the unit content; that's how
    the user inspects what would happen."""
    from agent.founder_loop.install import install
    ok, msg = install(dry_run=True)
    assert ok
    # The summary contains the unit-content section.
    assert "Unit content:" in msg
    assert "DRY RUN" in msg


def test_uninstall_dry_run_works():
    from agent.founder_loop.install import uninstall
    ok, msg = uninstall(dry_run=True)
    assert ok
    assert "DRY RUN" in msg


def test_status_returns_platform_info():
    from agent.founder_loop.install import status
    ok, msg = status()
    assert ok
    assert "Platform:" in msg
    assert "Unit path:" in msg
    assert "Installed:" in msg
