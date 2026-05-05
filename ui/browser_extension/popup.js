// popup.js — renders Tank widget + (optionally) the current Sublimation
// Card. "Tick now" forces a fresh tick.

const root = document.getElementById("fl-popup-root");
const statusEl = document.getElementById("fl-daemon-status");

async function render() {
  root.innerHTML = "<div class='fl-loading'>Loading…</div>";
  let today = null;
  let healthy = false;
  try {
    today = await FounderLoopAPI.today();
    healthy = true;
  } catch (err) {
    statusEl.textContent = "daemon: unreachable";
    root.innerHTML = `
      <div class="fl-loading">
        Daemon unreachable.<br><br>
        Start it with:<br>
        <code style="font-size:11px;color:#58a6ff">python -m agent loop serve …</code>
      </div>`;
    return;
  }

  const base = await FounderLoopAPI.getBase();
  statusEl.textContent = `daemon: ${base.replace("http://", "")}`;

  if (!today.tank) {
    root.innerHTML = `
      <div class="fl-loading">
        No contract bound for today.<br><br>
        Run:<br>
        <code style="font-size:11px;color:#58a6ff">python -m agent loop morning …</code>
      </div>`;
    return;
  }

  // Tank + priorities
  const tankWidget = FounderLoopUI.renderTankWidget(today.tank, today.contract);
  root.innerHTML = "";
  root.appendChild(tankWidget);

  // Try a dry-run tick to surface the current diagnosis, if any.
  let tick;
  try {
    tick = await FounderLoopAPI.tick({ dryRun: true });
  } catch (_) { /* not fatal */ }

  if (tick && tick.action) {
    const op = tick.action.op;
    if (op === "propose_constructive_expression" || op === "unlock_entertainment") {
      const diagnosis =
        (tick.action.payload && tick.action.payload.diagnosis) || null;
      const card = FounderLoopUI.renderSublimationCard(diagnosis, tick.action, {
        onAccept: async (i, opt) => {
          await FounderLoopAPI.logEvent({
            kind: "accepted_expression",
            expression_index: i,
            expression_action: opt.action,
            diagnosis_need: diagnosis ? diagnosis.underlying_need : null,
            source: "popup",
          });
          render();
        },
        onOverride: async () => {
          await FounderLoopAPI.logEvent({
            kind: "overrode_proposal",
            diagnosis_need: diagnosis ? diagnosis.underlying_need : null,
            source: "popup",
          });
          render();
        },
      });
      root.appendChild(card);
    }
  }
}

document.getElementById("fl-refresh").addEventListener("click", render);
document.getElementById("fl-tick-btn").addEventListener("click", async () => {
  try {
    await FounderLoopAPI.tick({ dryRun: false });
    chrome.runtime.sendMessage({ kind: "refresh_badge" }, () => {});
    render();
  } catch (err) {
    statusEl.textContent = "tick failed: " + err.message;
  }
});

// Settings
const settings = document.getElementById("fl-settings");
const settingsBtn = document.getElementById("fl-settings-btn");
const urlInput = document.getElementById("fl-daemon-url");
const saveBtn = document.getElementById("fl-save-settings");

settingsBtn.addEventListener("click", async () => {
  settings.classList.toggle("fl-hidden");
  if (!settings.classList.contains("fl-hidden")) {
    urlInput.value = await FounderLoopAPI.getBase();
  }
});
saveBtn.addEventListener("click", async () => {
  await FounderLoopAPI.setBase(urlInput.value.trim());
  settings.classList.add("fl-hidden");
  render();
});

render();
