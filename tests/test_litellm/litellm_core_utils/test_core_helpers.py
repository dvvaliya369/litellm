"""Tests for litellm_core_utils.core_helpers module."""

import pytest

from litellm.litellm_core_utils.core_helpers import map_finish_reason, reconstruct_model_name


def test_reconstruct_model_name_prefers_deployment_value():
    """Ensure deployment metadata wins when reconstructing the model name."""

    metadata = {"deployment": "vertex_ai/gemini-1.5-flash"}

    result = reconstruct_model_name(
        model_name="gemini-1.5-flash",
        custom_llm_provider="vertex_ai",
        metadata=metadata,
    )

    assert result == "vertex_ai/gemini-1.5-flash"


def test_reconstruct_model_name_adds_bedrock_prefix_when_missing():
    """Bedrock model names without prefixes should gain the provider prefix."""

    metadata = {}

    result = reconstruct_model_name(
        model_name="us.anthropic.claude-3-sonnet",
        custom_llm_provider="bedrock",
        metadata=metadata,
    )

    assert result == "bedrock/us.anthropic.claude-3-sonnet"


def test_reconstruct_model_name_returns_original_for_other_providers():
    """Non-Bedrock providers should not prepend anything."""

    metadata = {}

    result = reconstruct_model_name(
        model_name="claude-3-sonnet",
        custom_llm_provider="anthropic",
        metadata=metadata,
    )

    assert result == "claude-3-sonnet"


@pytest.mark.parametrize(
    "finish_reason",
    ["SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"],
)
def test_map_finish_reason_gemini_content_filter(finish_reason):
    """All Gemini content-filter finish reasons should map to 'content_filter'."""
    assert map_finish_reason(finish_reason) == "content_filter"


def test_map_finish_reason_gemini_stop():
    """STOP should map to 'stop'."""
    assert map_finish_reason("STOP") == "stop"


def test_map_finish_reason_gemini_max_tokens():
    """MAX_TOKENS should map to 'length'."""
    assert map_finish_reason("MAX_TOKENS") == "length"
