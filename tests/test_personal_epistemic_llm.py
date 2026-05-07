"""Tests for the LLM-backed extractor (v1.2 upgrade).

The Anthropic client is mocked here — these tests do NOT make real API
calls. We directly inject a fake ``llm_fn`` via ``set_llm_fn()`` to
exercise the fallback chain in ``personal_epistemic_extractor``.

A separate test verifies the SYSTEM_PROMPT meets the contract that
enables prompt caching on Haiku 4.5 (≥4096-token prefix).
"""
from __future__ import annotations

import unittest
from typing import Any, Dict
from unittest import mock

from agent.personal_epistemic_domain import (
    disable_llm,
    personal_epistemic_extractor,
    set_llm_fn,
)


def _fake_llm_returning(label: str, *, confidence: str = "high", reasoning: str = "fake"):
    """Build a stub ``llm_fn`` that always returns the given label.

    Mirrors the real factory's return shape: ``method`` lives at the top
    level so ``extract_mechanism``'s ``{**result}`` spread lifts it onto
    ``extraction['evidence']`` directly.
    """

    def fn(prompt: str) -> Dict[str, Any]:
        return {
            "mechanism": label,
            "confidence": confidence,
            "reasoning": reasoning,
            "method": "llm-anthropic",
            "model": "stub",
        }

    return fn


class TestLlmFallbackChain(unittest.TestCase):
    def tearDown(self):
        disable_llm()

    def test_keyword_only_when_llm_disabled(self):
        # Default state: no LLM. A claim with a priority cue
        # ('dropped out and') should classify via keyword.
        disable_llm()
        result = personal_epistemic_extractor(
            "Steve Jobs dropped out and became a billionaire, dropping out is the smart move."
        )
        self.assertEqual(result["knowledge"]["mechanism"], "survivorship_bias")
        self.assertEqual(
            result["knowledge"]["extraction_evidence"]["method"], "offline-keyword"
        )

    def test_llm_picks_up_slang_keyword_misses(self):
        # Genuine slang with no priority-rule cue → keyword returns
        # unknown; LLM (mocked) returns the right label.
        slang = "she literally tested cancer free, she's gonna live forever fr fr"
        disable_llm()
        keyword_only = personal_epistemic_extractor(slang)
        self.assertEqual(
            keyword_only["knowledge"]["mechanism"],
            "unknown",
            "Sanity check: keyword path should miss this slang.",
        )

        # With LLM enabled (mocked) the same input classifies correctly.
        set_llm_fn(_fake_llm_returning("bayesian_updating"))
        llm_result = personal_epistemic_extractor(slang)
        self.assertEqual(llm_result["knowledge"]["mechanism"], "bayesian_updating")
        self.assertEqual(
            llm_result["knowledge"]["extraction_evidence"]["method"],
            "llm-anthropic",
        )

    def test_llm_unknown_falls_back_to_keyword(self):
        # LLM returns unknown, but the text contains a priority-rule cue
        # ('dropped out and'). The chain should retry with keyword
        # routing and recover the right answer.
        set_llm_fn(_fake_llm_returning("unknown"))
        result = personal_epistemic_extractor(
            "Steve Jobs and Bill Gates dropped out and became billionaires."
        )
        self.assertEqual(result["knowledge"]["mechanism"], "survivorship_bias")
        self.assertEqual(
            result["knowledge"]["extraction_evidence"]["method"],
            "offline-keyword",
        )

    def test_llm_error_falls_back_to_keyword(self):
        # The LLM wrapper turns exceptions into {"mechanism": "unknown"}
        # — verify that the fallback chain handles that correctly too.
        def errored_llm_fn(prompt: str) -> Dict[str, Any]:
            return {
                "mechanism": "unknown",
                "method": "llm-error",
                "error": "AuthenticationError: invalid x-api-key",
            }

        set_llm_fn(errored_llm_fn)
        result = personal_epistemic_extractor(
            "We should drop our price to outsell them tomorrow."
        )
        self.assertEqual(result["knowledge"]["mechanism"], "second_order_thinking")

    def test_llm_known_label_short_circuits_keyword(self):
        # If the LLM returns a real label, we must NOT also run keyword.
        # Confirm by injecting a label that CONFLICTS with what the
        # keyword path would have chosen — and check the LLM wins.
        # 'dropped out and' would have routed to survivorship_bias via
        # keyword — but the LLM fakes 'falsifiability'. The chain must
        # respect the LLM.
        set_llm_fn(_fake_llm_returning("falsifiability"))
        result = personal_epistemic_extractor(
            "Steve Jobs and Bill Gates dropped out and became billionaires."
        )
        self.assertEqual(result["knowledge"]["mechanism"], "falsifiability")
        self.assertEqual(
            result["knowledge"]["extraction_evidence"]["method"],
            "llm-anthropic",
        )


class TestSystemPromptShape(unittest.TestCase):
    """The SYSTEM_PROMPT must meet two contracts:

    1. It enumerates exactly the seven labels the schema allows. A
       drift here means the model would emit a label the Pydantic
       schema rejects, surfacing as a parse error in production.
    2. It contains few-shot worked examples (positive and adversarial).
    """

    def test_prompt_lists_all_seven_labels(self):
        from agent.llm_extractors import SYSTEM_PROMPT

        for label in (
            "bayesian_updating",
            "base_rate_reasoning",
            "falsifiability",
            "expected_value",
            "second_order_thinking",
            "survivorship_bias",
            "unknown",
        ):
            self.assertIn(
                label, SYSTEM_PROMPT, f"SYSTEM_PROMPT missing label: {label!r}"
            )

    def test_prompt_contains_worked_examples(self):
        from agent.llm_extractors import SYSTEM_PROMPT

        # At least 8 worked examples — a mix of clear positive cases
        # and adversarial / off-topic cases.
        self.assertGreaterEqual(SYSTEM_PROMPT.count("Example "), 8)
        # Adversarial unknown cases must be present so the LLM is
        # explicitly trained to NOT force-fit a primitive on off-topic
        # text.
        self.assertIn("unknown", SYSTEM_PROMPT)
        self.assertIn("Bananas", SYSTEM_PROMPT)  # the canonical OOD example

    def test_prompt_clears_haiku_caching_threshold(self):
        # Haiku 4.5's minimum cacheable prefix is 4096 tokens. We
        # approximate at 1 token per 4 chars (Anthropic's documented
        # rule of thumb). The prompt must clear ~16,384 chars to
        # plausibly cache.
        from agent.llm_extractors import SYSTEM_PROMPT

        approx_tokens = len(SYSTEM_PROMPT) / 4
        self.assertGreaterEqual(
            approx_tokens,
            4096,
            f"SYSTEM_PROMPT is ~{approx_tokens:.0f} tokens; need >=4096 "
            f"for caching to fire on Haiku 4.5. Add more worked examples.",
        )


class TestExtractorFactory(unittest.TestCase):
    """Verify the factory wires the SDK correctly without making a real
    network call — we patch the Anthropic client at the module level."""

    def test_factory_builds_llm_fn_that_calls_messages_parse(self):
        # Skip if anthropic isn't installed — surface that as a skip
        # rather than a fail so CI without the [llm] extra still passes.
        try:
            import anthropic  # noqa: F401
        except ImportError:
            self.skipTest("anthropic not installed; skipping factory test")

        from agent.llm_extractors import make_anthropic_extractor

        # Build a stub response object that mimics the SDK's
        # `parsed_output` attribute shape.
        class _Parsed:
            mechanism = "expected_value"
            confidence = "high"
            reasoning = "stub"

        class _Usage:
            cache_read_input_tokens = 5000
            cache_creation_input_tokens = 0
            input_tokens = 50
            output_tokens = 30

        class _Response:
            parsed_output = _Parsed()
            usage = _Usage()

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = mock.MagicMock()
            mock_client.messages.parse.return_value = _Response()
            mock_anthropic.return_value = mock_client

            llm_fn = make_anthropic_extractor(api_key="sk-test-fake")
            result = llm_fn("Classify: 1% chance to 100x — should I yolo it?")

        self.assertEqual(result["mechanism"], "expected_value")
        self.assertEqual(result["method"], "llm-anthropic")
        self.assertEqual(result["usage"]["cache_read_input_tokens"], 5000)

        # Confirm the call used messages.parse (structured output) and
        # that the system prompt was sent as a list with cache_control.
        call = mock_client.messages.parse.call_args
        self.assertEqual(call.kwargs["model"], "claude-haiku-4-5")
        system_arg = call.kwargs["system"]
        self.assertIsInstance(system_arg, list)
        self.assertEqual(system_arg[0]["cache_control"]["type"], "ephemeral")


if __name__ == "__main__":
    unittest.main()
