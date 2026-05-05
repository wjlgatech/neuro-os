"""
Founder Loop tray app — cross-platform system tray icon (Linux,
macOS, Windows). Polls the local daemon every 60 seconds and renders
the current tank percent on the icon.

Menu items:

* Tank: NN% · ration X/Y min
* (date)
* — separator —
* Run tick now
* View today's contract
* Open daemon health
* — separator —
* Quit

Requires the ``[ui]`` extras::

    pip install -e ".[ui]"

Run::

    python -m ui.tray_app.tray --daemon http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Any, Dict, Optional

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    print(
        "founder_loop tray requires the [ui] extras: pip install -e \".[ui]\"\n"
        f"missing: {exc.name}",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


def _load_pystray():
    """Defer pystray import — its backend selection is eager and requires
    a display server. Importable without a display for headless tests."""
    try:
        import pystray as _ps  # noqa: WPS433
        return _ps
    except ImportError as exc:  # pragma: no cover
        print(
            "founder_loop tray requires the [ui] extras: "
            "pip install -e \".[ui]\"\n"
            f"missing: {exc.name}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


log = logging.getLogger("founder_loop.tray")

POLL_SECONDS = 60
ICON_SIZE = 64

COLOUR_BG = (13, 17, 23, 255)
COLOUR_RING = (139, 148, 158, 255)
COLOUR_BELOW = (210, 153, 34, 255)
COLOUR_OK = (86, 211, 100, 255)
COLOUR_OVER = (248, 81, 73, 255)
COLOUR_OFF = (110, 118, 129, 255)


# ---------------------------------------------------------------------------
# Daemon client
# ---------------------------------------------------------------------------


class DaemonClient:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def _get(self, path: str, timeout: float = 2.0) -> Dict[str, Any]:
        with urllib.request.urlopen(self.base + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def healthz(self) -> Optional[Dict[str, Any]]:
        try:
            return self._get("/healthz")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def today(self) -> Optional[Dict[str, Any]]:
        try:
            return self._get("/today")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def tick(self) -> Optional[Dict[str, Any]]:
        try:
            return self._get("/tick", timeout=10.0)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("tick failed: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Icon rendering
# ---------------------------------------------------------------------------


def render_icon(percent: Optional[float], status: Optional[str]) -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), COLOUR_BG)
    d = ImageDraw.Draw(img)

    pad = 6
    box = [pad, pad, ICON_SIZE - pad, ICON_SIZE - pad]
    stroke = 4

    # Outer ring
    d.ellipse(box, outline=COLOUR_RING, width=stroke)

    if percent is None:
        # Daemon offline — render a dim X.
        d.line([(pad + 8, pad + 8), (ICON_SIZE - pad - 8, ICON_SIZE - pad - 8)],
               fill=COLOUR_OFF, width=4)
        d.line([(pad + 8, ICON_SIZE - pad - 8), (ICON_SIZE - pad - 8, pad + 8)],
               fill=COLOUR_OFF, width=4)
        return img

    fill_colour = COLOUR_OK
    if status == "below_threshold":
        fill_colour = COLOUR_BELOW
    elif status == "threshold_over_ration":
        fill_colour = COLOUR_OVER

    # Fill: pieslice from bottom upward, proportional to percent.
    pct = max(0.0, min(100.0, float(percent)))
    if pct <= 0:
        pass  # empty ring
    else:
        # Render fill as a horizontal water-level: bottom y up to (1-pct/100).
        inner_pad = pad + stroke // 2
        x0 = inner_pad
        x1 = ICON_SIZE - inner_pad
        y_full = ICON_SIZE - inner_pad
        y_empty = inner_pad
        y_level = int(y_empty + (1 - pct / 100) * (y_full - y_empty))

        # Mask to the ring.
        mask = Image.new("L", (ICON_SIZE, ICON_SIZE), 0)
        ImageDraw.Draw(mask).ellipse(box, fill=255)

        fill = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        ImageDraw.Draw(fill).rectangle([x0, y_level, x1, y_full], fill=fill_colour)

        img = Image.composite(fill, img, mask)
        # Re-render the ring on top so it's not painted over.
        d2 = ImageDraw.Draw(img)
        d2.ellipse(box, outline=COLOUR_RING, width=stroke)

    return img


# ---------------------------------------------------------------------------
# Tray app
# ---------------------------------------------------------------------------


class TrayApp:
    def __init__(self, base: str) -> None:
        self.client = DaemonClient(base)
        self.base = base
        self._latest_today: Optional[Dict[str, Any]] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pystray = _load_pystray()

        self.icon = self._pystray.Icon(
            "founder_loop",
            render_icon(None, None),
            "Founder Loop",
            menu=self._build_menu(),
        )

    def _build_menu(self):
        def title_label(_):
            with self._lock:
                t = (self._latest_today or {}).get("tank")
            if not t:
                return "Daemon: offline"
            pct = round(t.get("percent") or 0)
            ration = t.get("ration_remaining_min")
            return f"Tank {pct}% · ration {ration} min"

        def date_label(_):
            with self._lock:
                today = self._latest_today or {}
            return today.get("date") or "—"

        def status_label(_):
            with self._lock:
                t = (self._latest_today or {}).get("tank") or {}
            return f"Status: {t.get('status') or 'unknown'}"

        return self._pystray.Menu(
            self._pystray.MenuItem(title_label, None, enabled=False),
            self._pystray.MenuItem(date_label, None, enabled=False),
            self._pystray.MenuItem(status_label, None, enabled=False),
            self._pystray.Menu.SEPARATOR,
            self._pystray.MenuItem("Run tick now", self._on_tick),
            self._pystray.MenuItem("Show contract", self._on_show_contract),
            self._pystray.MenuItem("Open daemon health", self._on_open_health),
            self._pystray.Menu.SEPARATOR,
            self._pystray.MenuItem("Quit", self._on_quit),
        )

    # ---------- Menu actions ----------

    def _on_tick(self, _icon, _item):
        result = self.client.tick()
        if result and "tick" in result:
            op = result["tick"]["action"]["op"]
            self.icon.notify(f"Tick: {op}", "Founder Loop")
        else:
            self.icon.notify("Tick failed (daemon down?)", "Founder Loop")
        self._refresh()

    def _on_show_contract(self, _icon, _item):
        with self._lock:
            today = self._latest_today or {}
        contract = today.get("contract")
        if not contract:
            self.icon.notify("No contract bound", "Founder Loop")
            return
        priorities = contract.get("priorities") or []
        lines = []
        for p in priorities:
            mark = "●" if p.get("status") == "evidenced" else "○"
            lines.append(f"{mark} {p['title']} ({p['evidence_type']})")
        msg = (
            "\n".join(lines) +
            f"\nration: {contract.get('entertainment_ration_min')} min · "
            f"threshold: {contract.get('threshold_pct')}%"
        )
        self.icon.notify(msg, f"Today: {contract.get('date')}")

    def _on_open_health(self, _icon, _item):
        webbrowser.open(self.base + "/healthz")

    def _on_quit(self, _icon, _item):
        self._stop.set()
        self.icon.stop()

    # ---------- Polling ----------

    def _refresh(self) -> None:
        today = self.client.today()
        with self._lock:
            self._latest_today = today
        if today and today.get("tank"):
            tank = today["tank"]
            self.icon.icon = render_icon(tank.get("percent"), tank.get("status"))
        else:
            self.icon.icon = render_icon(None, None)

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            self._refresh()
            self._stop.wait(POLL_SECONDS)

    def run(self) -> None:
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self.icon.run()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="founder_loop-tray")
    p.add_argument("--daemon", default="http://127.0.0.1:8765",
                   help="founder_loop daemon URL (default: http://127.0.0.1:8765)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    TrayApp(args.daemon).run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
