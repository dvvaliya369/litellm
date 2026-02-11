# Content Filter Finish Reason Mismatch Analysis

## Issue Summary

There is a **mismatch** between the finish reasons defined in `get_flagged_finish_reasons()` and those in `get_finish_reason_mapping()` in the Vertex AI Gemini implementation.

## The Problem

### Two Key Methods:

1. **`get_flagged_finish_reasons()`** (Line 1186-1200)
   - Returns finish reasons that indicate a content policy violation
   - Used to detect if a response should be handled as blocked/filtered
   - Current values: `SAFETY`, `RECITATION`, `BLOCKLIST`, `PROHIBITED_CONTENT`, `SPII`, `IMAGE_SAFETY`

2. **`get_finish_reason_mapping()`** (Line 1202-1220)
   - Maps Vertex AI finish reasons to OpenAI-compatible finish reasons
   - Used by `_check_finish_reason()` to translate finish reasons
   - Includes: `SAFETY`, `RECITATION`, `LANGUAGE`, `OTHER`, `BLOCKLIST`, `PROHIBITED_CONTENT`, `SPII`, `IMAGE_SAFETY`

### The Mismatch:

**Missing from `get_flagged_finish_reasons()`:**
- ❌ `LANGUAGE` - Present in mapping but NOT in flagged reasons
- ❌ `OTHER` - Present in mapping but NOT in flagged reasons

These finish reasons are mapped to `content_filter` in the mapping, but they are NOT included in the flagged finish reasons dictionary.

## Impact Analysis

### Current Code Flow:

1. **Non-streaming response** (`transform_response()` at line 2186-2196):
   ```python
   _candidates = completion_response.get("candidates")
   if _candidates and len(_candidates) > 0:
       content_policy_violations = (
           VertexGeminiConfig().get_flagged_finish_reasons()
       )
       if (
           "finishReason" in _candidates[0]
           and _candidates[0]["finishReason"] in content_policy_violations.keys()
       ):
           return self._handle_content_policy_violation(...)
   ```

2. **If finishReason is `LANGUAGE` or `OTHER`:**
   - ❌ NOT detected as content policy violation (line 2193 check fails)
   - ✓ Continues to `_process_candidates()` 
   - ✓ `_check_finish_reason()` correctly maps to `content_filter` (line 2119)
   - ✓ Response has `finish_reason="content_filter"` in choices

3. **However, the response is NOT handled specially:**
   - The response goes through normal processing instead of `_handle_content_policy_violation()`
   - This means the content might be included when it should be filtered
   - Inconsistent behavior compared to other content filter reasons

### What Should Happen:

When `finishReason` is `LANGUAGE` or `OTHER`:
- Should be detected as a content policy violation
- Should call `_handle_content_policy_violation()` which:
  - Sets `finish_reason="content_filter"`
  - Sets `content=None` in the message
  - Properly extracts usage metadata

## Root Cause

The `get_flagged_finish_reasons()` method is incomplete. It should include ALL finish reasons that represent content filtering, not just a subset.

## Verification

Looking at the `map_finish_reason()` function in `litellm/litellm_core_utils/core_helpers.py` (lines 87-95):

```python
elif finish_reason in (
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
):  # vertex ai / gemini
    return "content_filter"
```

This also doesn't include `LANGUAGE` or `OTHER`, which creates another inconsistency.

## Recommendation

### Fix 1: Update `get_flagged_finish_reasons()` 

Add `LANGUAGE` and `OTHER` to the flagged finish reasons dictionary:

```python
def get_flagged_finish_reasons(self) -> Dict[str, str]:
    """
    Return Dictionary of finish reasons which indicate response was flagged
    and what it means
    """
    return {
        "SAFETY": "The token generation was stopped as the response was flagged for safety reasons. NOTE: When streaming the Candidate.content will be empty if content filters blocked the output.",
        "RECITATION": "The token generation was stopped as the response was flagged for unauthorized citations.",
        "BLOCKLIST": "The token generation was stopped as the response was flagged for the terms which are included from the terminology blocklist.",
        "PROHIBITED_CONTENT": "The token generation was stopped as the response was flagged for the prohibited contents.",
        "SPII": "The token generation was stopped as the response was flagged for Sensitive Personally Identifiable Information (SPII) contents.",
        "IMAGE_SAFETY": "The token generation was stopped as the response was flagged for image safety reasons.",
        "LANGUAGE": "The token generation was stopped as the response was flagged for language-related reasons.",  # ADD THIS
        "OTHER": "The token generation was stopped for other content filtering reasons.",  # ADD THIS
    }
```

### Fix 2: Update `map_finish_reason()` in core_helpers.py

Add `LANGUAGE` and `OTHER` to the content filter mapping:

```python
elif finish_reason in (
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
    "LANGUAGE",  # ADD THIS
    "OTHER",     # ADD THIS
):  # vertex ai / gemini
    return "content_filter"
```

## Test Coverage

The test `test_all_flagged_finish_reasons_in_mapping()` at line 631 should catch this issue:

```python
def test_all_flagged_finish_reasons_in_mapping():
    """
    Test that all flagged finish reasons are also present in the finish reason mapping
    and map to 'content_filter'.
    """
    flagged = VertexGeminiConfig().get_flagged_finish_reasons()
    mapping = VertexGeminiConfig.get_finish_reason_mapping()
    for reason in flagged:
        assert reason in mapping, f"{reason} is flagged but not in finish reason mapping"
        assert mapping[reason] == "content_filter", f"{reason} should map to 'content_filter'"
```

However, this test checks if flagged reasons are in the mapping, not the reverse. The issue is that `LANGUAGE` and `OTHER` are in the mapping but NOT in the flagged reasons.

## Conclusion

**Yes, there is a mismatch.** The `LANGUAGE` and `OTHER` finish reasons are:
- ✓ Present in `get_finish_reason_mapping()` and mapped to `content_filter`
- ❌ Missing from `get_flagged_finish_reasons()`
- ❌ Missing from `map_finish_reason()` in core_helpers.py

This causes inconsistent handling where responses with `finishReason="LANGUAGE"` or `finishReason="OTHER"` are not properly detected as content policy violations and may not have their content properly filtered.
