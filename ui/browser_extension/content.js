// content.js — injected on distraction hosts. Calls /tick, and if the
// loop diagnoses an underlying need, mounts the Sublimation Card.
//
// Honors agency: never blocks navigation. The overlay is dismissable
// and "proceed anyway" is always present.

(async function () {
  // Only run on the top frame; nested iframes (embeds) get noisy.
  if (window.top !== window) return;

  // Don't double-mount on SPA navigations.
  if (document.getElementById("fl-overlay-root")) return;

  let tick;
  try {
    tick = await FounderLoopAPI.tick({ dryRun: true });
  } catch (err) {
    // Daemon unreachable. Be silent — the user shouldn't see "your
    // productivity assistant is broken" overlays on YouTube.
    console.debug("[founder_loop] daemon unreachable:", err.message);
    return;
  }

  const action = tick && tick.action;
  if (!action) return;

  // Two interesting cases:
  //   propose_constructive_expression  → render card (pre-threshold urge)
  //   unlock_entertainment             → small toast (within ration)
  if (action.op === "propose_constructive_expression") {
    mountCard(tick);
  } else if (action.op === "unlock_entertainment") {
    mountUnlockToast(tick);
  }
  // Other ops (continue, escalate, etc.) → do nothing on this surface.
})();

function mountCard(tick) {
  const action = tick.action;
  const diagnosis = (action.payload && action.payload.diagnosis) || null;

  const root = document.createElement("div");
  root.id = "fl-overlay-root";

  const dismiss = (reason) => {
    if (root.parentNode) root.parentNode.removeChild(root);
    // Log the resolution.
    FounderLoopAPI.logEvent({
      kind: reason === "override" ? "overrode_proposal" : "accepted_expression",
      ...reason,
    }).catch((e) => console.debug("[founder_loop] event log failed:", e));
  };

  const card = FounderLoopUI.renderSublimationCard(diagnosis, action, {
    onAccept: (i, opt) => {
      FounderLoopAPI.logEvent({
        kind: "accepted_expression",
        expression_index: i,
        expression_action: opt.action,
        diagnosis_need: diagnosis ? diagnosis.underlying_need : null,
        host: location.host,
      }).catch((e) => console.debug("[founder_loop] event log failed:", e));
      if (root.parentNode) root.parentNode.removeChild(root);
      // Best-effort: navigate the user back to the previous page so
      // YouTube doesn't auto-play. We don't FORCE this; if there's no
      // history, the page just stays.
      if (window.history.length > 1) {
        window.history.back();
      }
    },
    onOverride: () => {
      FounderLoopAPI.logEvent({
        kind: "overrode_proposal",
        diagnosis_need: diagnosis ? diagnosis.underlying_need : null,
        host: location.host,
      }).catch((e) => console.debug("[founder_loop] event log failed:", e));
      if (root.parentNode) root.parentNode.removeChild(root);
    },
  });

  root.appendChild(card);

  // Click outside the card → treat as "I'll think about it"; dismiss
  // without logging accept/override.
  root.addEventListener("click", (e) => {
    if (e.target === root) {
      if (root.parentNode) root.parentNode.removeChild(root);
    }
  });

  // ESC also dismisses without logging.
  document.addEventListener(
    "keydown",
    (e) => {
      if (e.key === "Escape" && root.parentNode) {
        root.parentNode.removeChild(root);
      }
    },
    { once: true }
  );

  document.documentElement.appendChild(root);
  // Best-effort: log that we showed the card on this host.
  FounderLoopAPI.logEvent({
    kind: "opened_distraction_url",
    host: location.host,
    diagnosis_need: diagnosis ? diagnosis.underlying_need : null,
  }).catch(() => {});
}

function mountUnlockToast(tick) {
  const tank = tick.tank || {};
  const toast = document.createElement("div");
  toast.id = "fl-unlock-toast";
  Object.assign(toast.style, {
    position: "fixed",
    bottom: "24px",
    right: "24px",
    zIndex: "2147483647",
    background: "#0d1117",
    color: "#56d364",
    border: "1px solid #2ea043",
    borderRadius: "10px",
    padding: "10px 14px",
    font: "13px -apple-system, system-ui, sans-serif",
    boxShadow: "0 8px 24px rgba(0,0,0,.4)",
    animation: "fl-toast-in 200ms ease-out",
  });
  toast.textContent = `You earned this — ${tank.ration_remaining_min || 0} min ration left.`;
  document.documentElement.appendChild(toast);
  setTimeout(() => {
    if (toast.parentNode) toast.parentNode.removeChild(toast);
  }, 4000);
}
