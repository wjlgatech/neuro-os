// newtab.js — full landing page rendered on every new tab. Tank,
// priorities, current diagnosis (if any), recent ticks.

const greeting = document.getElementById("fl-greeting");
const dateEl = document.getElementById("fl-date");
const tankSection = document.getElementById("fl-tank-section");
const cardSection = document.getElementById("fl-card-section");
const prioritiesSection = document.getElementById("fl-priorities-section");
const prioritiesList = document.getElementById("fl-priorities-list");
const recentSection = document.getElementById("fl-recent-section");
const recentList = document.getElementById("fl-recent-list");
const statusEl = document.getElementById("fl-daemon-status");

dateEl.textContent = new Date().toLocaleDateString(undefined, {
  weekday: "long",
  year: "numeric",
  month: "long",
  day: "numeric",
});

(async function render() {
  greeting.textContent = greetingText();

  let today;
  try {
    today = await FounderLoopAPI.today();
  } catch (err) {
    statusEl.textContent = "daemon: unreachable";
    tankSection.classList.remove("fl-loading");
    tankSection.innerHTML = `
      <div style="font-size:13px;color:#8b949e;text-align:center;padding:24px">
        Daemon unreachable.<br>
        Start it with <code style="color:#58a6ff">python -m agent loop serve …</code>
      </div>`;
    return;
  }

  const base = await FounderLoopAPI.getBase();
  statusEl.textContent = `daemon: ${base.replace("http://", "")}`;

  // Tank
  tankSection.classList.remove("fl-loading");
  tankSection.innerHTML = "";
  if (!today.tank) {
    tankSection.innerHTML = `
      <div style="font-size:13px;color:#8b949e;text-align:center;padding:24px">
        No contract bound for today.<br>
        Run <code style="color:#58a6ff">python -m agent loop morning …</code>
      </div>`;
    return;
  }
  const tank = FounderLoopUI.renderTankWidget(today.tank, today.contract);
  tankSection.appendChild(tank);

  // Priorities (separate card so it gets its own header)
  if (today.contract && today.contract.priorities) {
    prioritiesList.innerHTML = "";
    today.contract.priorities.forEach((p) => {
      const li = document.createElement("li");
      li.className = "fl-priority";
      li.dataset.status = p.status;
      const dot = document.createElement("span");
      dot.className = "fl-priority-dot";
      dot.textContent = p.status === "evidenced" ? "●" : "○";
      const t = document.createElement("span");
      t.className = "fl-priority-title";
      t.textContent = p.title;
      const e = document.createElement("span");
      e.className = "fl-priority-evidence";
      e.textContent = `(${p.evidence_type})`;
      li.appendChild(dot);
      li.appendChild(t);
      li.appendChild(e);
      prioritiesList.appendChild(li);
    });
    prioritiesSection.classList.remove("fl-hidden");
  }

  // Recent ticks
  if (today.recent_ticks && today.recent_ticks.length) {
    recentList.innerHTML = "";
    today.recent_ticks.forEach((row) => {
      const li = document.createElement("li");
      const ts = ((row.state || {}).timestamp || row.ts || "")
        .slice(11, 16); // HH:MM
      const op = (row.action || {}).op || "?";
      const t = document.createElement("span");
      t.className = "fl-recent-time";
      t.textContent = ts;
      const o = document.createElement("span");
      o.className = "fl-recent-op";
      o.textContent = FounderLoopUI.humanize(op);
      li.appendChild(t);
      li.appendChild(o);
      const rationale = (row.action || {}).rationale;
      if (rationale) {
        const r = document.createElement("span");
        r.style.color = "#8b949e";
        r.style.marginLeft = "8px";
        r.textContent = "— " + rationale;
        li.appendChild(r);
      }
      recentList.appendChild(li);
    });
    recentSection.classList.remove("fl-hidden");
  }

  // Show the live diagnosis (if any)
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
            source: "newtab",
          });
          location.reload();
        },
        onOverride: async () => {
          await FounderLoopAPI.logEvent({
            kind: "overrode_proposal",
            diagnosis_need: diagnosis ? diagnosis.underlying_need : null,
            source: "newtab",
          });
          location.reload();
        },
      });
      cardSection.classList.remove("fl-hidden");
      cardSection.innerHTML = "";
      cardSection.appendChild(card);
    }
  }
})();

function greetingText() {
  const h = new Date().getHours();
  if (h < 5) return "Late night.";
  if (h < 12) return "Good morning.";
  if (h < 18) return "Afternoon check-in.";
  if (h < 22) return "Evening.";
  return "Wind down.";
}
