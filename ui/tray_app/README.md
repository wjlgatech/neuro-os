# Founder Loop — system tray app

Cross-platform tray icon (Linux / macOS / Windows) that polls the local
`founder_loop` daemon every 60 seconds and renders the current tank
percent in your menu bar.

## Install

The tray app needs `pystray` and `Pillow`. They're in the optional
`[ui]` extras::

    pip install -e ".[ui]"

On Linux you also need an X11 / Wayland tray host. GNOME 3.26+ removed
the legacy tray; use the `AppIndicator and KStatusNotifierItem Support`
GNOME extension or run on KDE / XFCE / etc. directly.

## Run

Start the daemon first (in another terminal)::

    neuro-os start

That picks up `~/.founder_loop/*` defaults and auto-detects workflowx.
Then launch the tray::

    python -m ui.tray_app.tray

Optional: point at a non-default daemon URL::

    python -m ui.tray_app.tray --daemon http://127.0.0.1:9001

## Menu

```
Tank 60% · ration 0/60 min      ← live tank %
2026-05-05                       ← today's date
Status: below_threshold          ← contract status
─────────────────────────────────
Run tick now                     ← writes a real tick to the registry
Show contract                    ← OS notification with priorities
Open daemon health               ← opens /healthz in browser
─────────────────────────────────
Quit
```

The icon glyph is a "tank gauge": water-level fill in green
(within ration), amber (below threshold), or red (ration over). When
the daemon is unreachable the icon shows a dim X.

## Icon at a glance

| Status | Glyph |
|---|---|
| `below_threshold` | amber half-fill |
| `threshold_within_ration` | green fill |
| `threshold_over_ration` | red fill |
| daemon down | dim X |
