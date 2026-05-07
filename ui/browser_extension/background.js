// background.js — service worker. Polls the daemon every 5 minutes,
// updates the badge text with the current tank percent.

const POLL_ALARM = "fl_poll_tank";
const POLL_PERIOD_MIN = 5;

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(POLL_ALARM, { periodInMinutes: POLL_PERIOD_MIN });
  refreshBadge();
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(POLL_ALARM, { periodInMinutes: POLL_PERIOD_MIN });
  refreshBadge();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === POLL_ALARM) refreshBadge();
});

// Allow popup/newtab to trigger an immediate refresh.
chrome.runtime.onMessage.addListener((msg, _sender, send) => {
  if (msg && msg.kind === "refresh_badge") {
    refreshBadge().then(() => send({ ok: true }));
    return true; // async
  }
});

async function refreshBadge() {
  const base = await getDaemonBase();
  let tank = null;
  try {
    const res = await fetch(base + "/tank");
    if (res.ok) {
      const j = await res.json();
      tank = j.tank;
    }
  } catch (_) {
    // Daemon down. Show a dim "off" badge.
  }

  if (!tank) {
    await chrome.action.setBadgeText({ text: "off" });
    await chrome.action.setBadgeBackgroundColor({ color: "#6e7681" });
    await chrome.action.setTitle({
      title: "Founder Loop — daemon unreachable. Run `python -m agent loop serve ...`",
    });
    return;
  }

  const pct = Math.round(tank.percent || 0);
  await chrome.action.setBadgeText({ text: String(pct) });
  await chrome.action.setBadgeBackgroundColor({
    color: badgeColorFor(tank.status),
  });
  await chrome.action.setTitle({
    title: `Founder Loop — tank ${pct}% · ration ${tank.ration_remaining_min} min left · ${tank.status}`,
  });
}

function badgeColorFor(status) {
  switch (status) {
    case "threshold_within_ration":
      return "#2ea043"; // green: enjoy your ration
    case "threshold_over_ration":
      return "#f85149"; // red: ration burnt
    case "below_threshold":
    default:
      return "#d29922"; // amber: keep going
  }
}

async function getDaemonBase() {
  const { daemonBase } = await chrome.storage.local.get("daemonBase");
  return daemonBase || "http://127.0.0.1:8765";
}
