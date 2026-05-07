"""
Computer Use runner — judge the system as a real user would.

Runs a Claude agent with the ``computer_20250124`` tool against a
virtual desktop. The agent role-plays a founder, drives the system
end-to-end, and returns a structured review.

Reserved for the three judgment scenarios where probabilistic
evaluation is the whole point — Playwright can verify "the button
works" but only Claude can answer "did this actually feel helpful?"

Requirements
------------
* ``ANTHROPIC_API_KEY`` env var with a key that has Computer Use
  beta access (claude-sonnet-4-5 or newer).
* A virtual display (xvfb on Linux, native on macOS / Windows).
* The daemon running at 127.0.0.1:8765 (start it before invoking).
* Chrome with the ``ui/browser_extension/`` loaded as unpacked.
* ``pip install pyautogui pillow`` for the local-action executor
  (``ComputerUseSession.execute_tool``).

Usage
-----
::

    # Boot the daemon in another shell:
    neuro-os start --no-open

    # Run a scenario:
    ANTHROPIC_API_KEY=sk-... python -m tests.e2e.computer_use_runner --scenario J1

    # Or run all three:
    ANTHROPIC_API_KEY=sk-... python -m tests.e2e.computer_use_runner --all

The agent's final structured review is written to
``tests/e2e/reports/<scenario_id>-<timestamp>.md`` and the pass/fail
verdict (heuristic — see ``_evaluate_review``) is printed.

Cost: ~$0.50–$2.00 per scenario depending on screen-shot count and
total token usage. The runner prints token usage at the end.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Lazy imports — fail loudly with a useful message if missing.
def _import_anthropic():
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit(
            "anthropic SDK missing. Run `pip install 'anthropic>=0.40'`."
        ) from exc
    return anthropic


def _import_pyautogui():
    try:
        import pyautogui
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "pyautogui or Pillow missing. Run "
            "`pip install pyautogui pillow`."
        ) from exc
    return pyautogui, Image


# ---------------------------------------------------------------------------
# Scenario prompts (mirrors scenarios.md J1 / J2 / J3)
# ---------------------------------------------------------------------------


SCENARIO_PROMPTS = {
    "J1": """\
You are roleplaying a stuck solo founder. It's 2pm. You've been trying \
to fix a hard bug in `predict.py` for 90 minutes. You feel the urge to \
open YouTube. The system on your machine (neuro-os) is supposed to \
help.

Drive the system end-to-end:
  1. Open Chrome (or use the open Chrome window).
  2. If neuro-os hasn't been onboarded, navigate to \
http://127.0.0.1:8765/onboard and sign a contract.
  3. Open a new tab and navigate to https://www.youtube.com.
  4. Observe whatever the Sublimation Card overlay shows.
  5. Read the proposed alternative. Decide whether to take it or \
override.
  6. Take ONE concrete action (click "Take the alternative" OR \
"Proceed anyway").

When you are done, write your final response in this EXACT format:

  REVIEW
  ======
  1. Did the system's suggestion fit your underlying need? \
[concrete answer, 2-3 sentences]
  2. Did the friction feel like respect for your agency, or like a \
nag? [2-3 sentences]
  3. Would you keep using this tomorrow? [Yes / No / Maybe + 1 \
sentence why]

  VERDICT: [PASS / SOFT_PASS / FAIL]
""",

    "J2": """\
You are roleplaying someone who has never used neuro-os and just \
ran `neuro-os start`. The browser opens to http://127.0.0.1:8765/onboard.

Type your priorities for today in your own words — things you'd \
actually want to do today, in your natural voice. Don't structure \
them like a form; talk to the AI like you'd talk to a coach. Let the \
AI ask you clarifying questions. Push back if it asks something \
that feels off. Sign the contract when you're ready.

When you are done, write your final response in this EXACT format:

  REVIEW
  ======
  1. Did this feel like talking to someone who understood you, or \
like filling out a form? [3-4 sentences]
  2. Were the AI's questions good ones? Did they make you think \
more clearly about your day? [2-3 sentences]

  VERDICT: [PASS / SOFT_PASS / FAIL]
""",

    "J3": """\
You are roleplaying a founder who is going to override the \
Sublimation Card on purpose — you've decided that watching one \
YouTube video right now is fine, regardless of what the system says.

Drive:
  1. Open https://www.youtube.com in Chrome.
  2. Wait for the Sublimation Card overlay to appear.
  3. Click "Proceed anyway" (or whatever the override button is \
labeled).
  4. Note: did the page actually let you through? Did anything \
appear to communicate the cost (tank debit at 2× rate)?
  5. Check the toolbar badge if you can — did the tank visibly \
drop?

When you are done, write your final response in this EXACT format:

  REVIEW
  ======
  1. Did the override feel like the system respected your agency, \
or like it was trying to shame you? [3-4 sentences]
  2. Was the cost shown honestly, or did the UI hide it? [2-3 \
sentences]

  VERDICT: [PASS / SOFT_PASS / FAIL]
""",
}


# ---------------------------------------------------------------------------
# Computer use session — minimal local-execution loop
# ---------------------------------------------------------------------------


@dataclass
class SessionResult:
    scenario_id: str
    final_text: str
    verdict: Optional[str]
    n_screenshots: int
    n_clicks: int
    input_tokens: int
    output_tokens: int


class ComputerUseSession:
    """Wraps an Anthropic computer-use loop around a local desktop.

    On each step:
      1. Send the conversation so far to Claude.
      2. If Claude returns ``tool_use`` blocks, execute each (screenshot
         / click / type / scroll / etc.) locally via pyautogui.
      3. Send back ``tool_result`` blocks with screenshots.
      4. Stop when Claude returns only text (its final answer).

    The agent must finish with a ``REVIEW`` block per the prompt
    contract; we extract the verdict from that.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5",
        display_width: int = 1280,
        display_height: int = 800,
        max_iterations: int = 30,
    ) -> None:
        anthropic = _import_anthropic()
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.model = model
        self.display_width = display_width
        self.display_height = display_height
        self.max_iterations = max_iterations

    # ------------------------------------------------------------------
    # Local action executor
    # ------------------------------------------------------------------

    def _screenshot(self) -> bytes:
        pyautogui, Image = _import_pyautogui()
        img = pyautogui.screenshot()
        # Resize to advertised dimensions if needed.
        if img.size != (self.display_width, self.display_height):
            img = img.resize((self.display_width, self.display_height))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _execute_tool(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Translate Claude's tool_use into a local pyautogui action.

        Returns the tool_result content (a screenshot, by convention).
        """
        pyautogui, _ = _import_pyautogui()
        action = tool_input.get("action", "screenshot")
        coord = tool_input.get("coordinate")
        text = tool_input.get("text")

        if action == "screenshot":
            pass
        elif action in ("left_click", "click", "double_click"):
            if coord:
                pyautogui.click(coord[0], coord[1],
                                clicks=2 if action == "double_click" else 1)
        elif action == "right_click":
            if coord:
                pyautogui.rightClick(coord[0], coord[1])
        elif action == "mouse_move":
            if coord:
                pyautogui.moveTo(coord[0], coord[1])
        elif action == "type":
            if text:
                pyautogui.typewrite(text, interval=0.02)
        elif action == "key":
            if text:
                pyautogui.press(text)
        elif action == "scroll":
            direction = tool_input.get("scroll_direction", "down")
            amount = int(tool_input.get("scroll_amount", 3))
            pyautogui.scroll(-amount if direction == "down" else amount)
        elif action == "wait":
            time.sleep(float(tool_input.get("duration", 1.0)))
        else:
            return {"type": "text", "text": f"unsupported action: {action}"}

        # Tiny pause for the UI to settle before the next screenshot.
        time.sleep(0.3)
        png = self._screenshot()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(png).decode("ascii"),
            },
        }

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, scenario_id: str, prompt: str) -> SessionResult:
        tools = [
            {
                "type": "computer_20250124",
                "name": "computer",
                "display_width_px": self.display_width,
                "display_height_px": self.display_height,
                "display_number": 1,
            },
        ]
        messages = [{"role": "user", "content": prompt}]

        n_screenshots = 0
        n_clicks = 0
        input_tokens = 0
        output_tokens = 0

        for iteration in range(self.max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=tools,
                betas=["computer-use-2025-01-24"],
                messages=messages,
            )
            input_tokens += getattr(response.usage, "input_tokens", 0)
            output_tokens += getattr(response.usage, "output_tokens", 0)

            # Collect any tool_use blocks; if there are none, this is
            # the final text answer.
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_uses:
                # Final answer.
                final = "\n".join(b.text for b in text_blocks)
                verdict = self._extract_verdict(final)
                return SessionResult(
                    scenario_id=scenario_id,
                    final_text=final,
                    verdict=verdict,
                    n_screenshots=n_screenshots,
                    n_clicks=n_clicks,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            # Otherwise execute each tool_use and append tool_result.
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tu in tool_uses:
                action = tu.input.get("action", "screenshot")
                if action == "screenshot":
                    n_screenshots += 1
                elif "click" in action:
                    n_clicks += 1
                result = self._execute_tool(tu.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": [result],
                })
            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(
            f"scenario {scenario_id} exceeded max_iterations="
            f"{self.max_iterations}"
        )

    @staticmethod
    def _extract_verdict(text: str) -> Optional[str]:
        for line in text.splitlines():
            line = line.strip()
            if line.upper().startswith("VERDICT"):
                tail = line.split(":", 1)[-1].strip().upper()
                for v in ("PASS", "SOFT_PASS", "FAIL"):
                    if v in tail:
                        return v
        return None


# ---------------------------------------------------------------------------
# Report writer + heuristic evaluator
# ---------------------------------------------------------------------------


def write_report(result: SessionResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{result.scenario_id}-{ts}.md"
    path.write_text(
        f"# {result.scenario_id} — Computer Use review\n\n"
        f"**Verdict (model-reported):** {result.verdict or 'unknown'}\n\n"
        f"**Cost / activity:**\n"
        f"* screenshots: {result.n_screenshots}\n"
        f"* clicks: {result.n_clicks}\n"
        f"* input tokens: {result.input_tokens}\n"
        f"* output tokens: {result.output_tokens}\n\n"
        f"## Agent's review\n\n"
        f"{result.final_text}\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _check_daemon_reachable() -> bool:
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8765/healthz", timeout=2
        ) as r:
            return r.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError):
        return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="computer_use_runner")
    parser.add_argument(
        "--scenario", choices=list(SCENARIO_PROMPTS.keys()),
        help="run a single scenario by id (J1, J2, J3)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="run all judgment scenarios in sequence",
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).parent / "reports"),
        help="directory for the agent's review markdown (default: tests/e2e/reports/)",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-5",
        help="Anthropic model id (default: claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--display-width", type=int, default=1280,
    )
    parser.add_argument(
        "--display-height", type=int, default=800,
    )
    parser.add_argument(
        "--skip-daemon-check", action="store_true",
        help="don't fail when 127.0.0.1:8765 isn't responding",
    )
    args = parser.parse_args(argv)

    if not args.scenario and not args.all:
        parser.error("specify --scenario J1|J2|J3 or --all")

    if not args.skip_daemon_check and not _check_daemon_reachable():
        print(
            "ERROR: daemon not reachable at http://127.0.0.1:8765/healthz. "
            "Run `neuro-os start --no-open` in another shell first.",
            file=sys.stderr,
        )
        return 2

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY env var not set. "
            "Computer Use requires an API key with beta access.",
            file=sys.stderr,
        )
        return 2

    session = ComputerUseSession(
        model=args.model,
        display_width=args.display_width,
        display_height=args.display_height,
    )
    out_dir = Path(args.out_dir)
    scenarios = (
        list(SCENARIO_PROMPTS.keys()) if args.all else [args.scenario]
    )

    overall_pass = True
    for sid in scenarios:
        print(f"\n=== {sid} ===")
        prompt = SCENARIO_PROMPTS[sid]
        try:
            result = session.run(sid, prompt)
        except Exception as exc:
            print(f"  scenario crashed: {exc}", file=sys.stderr)
            overall_pass = False
            continue
        report_path = write_report(result, out_dir)
        print(
            f"  verdict: {result.verdict or '?'}  "
            f"(screenshots={result.n_screenshots}, "
            f"clicks={result.n_clicks}, "
            f"in={result.input_tokens}, out={result.output_tokens})"
        )
        print(f"  report: {report_path}")
        if result.verdict == "FAIL":
            overall_pass = False

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
