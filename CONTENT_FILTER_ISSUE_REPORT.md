# Content Filter Finish Reason Mismatch - Issue Report

## Executive Summary

**YES, there is a mismatch in the content filter handling.** Two finish reasons (`LANGUAGE` and `OTHER`) are mapped to `content_filter` but are NOT included in the flagged finish reasons list, causing inconsistent handling of content policy violations.

---

## The Mismatch

### File: `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py`

#### Method 1: `get_flagged_finish_reasons()` (Lines 1186-1200)

**Purpose:** Returns finish reasons that indicate a content policy violation  
**Used by:** `transform_response()` to detect if response should be handled as blocked/filtered

**Current values:**
```python
{
    "SAFETY": "...",
    "RECITATION": "...",
    "BLOCKLIST": "...",
    "PROHIBITED_CONTENT": "...",
    "SPII": "...",
    "IMAGE_SAFETY": "..."
}
```

**Missing:** `LANGUAGE`, `OTHER`

---

#### Method 2: `get_finish_reason_mapping()` (Lines 1202-1220)

**Purpose:** Maps Vertex AI finish reasons to OpenAI-compatible format  
**Used by:** `_check_finish_reason()` to translate finish reasons

**Content filter mappings:**
```python
{
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "LANGUAGE": "content_filter",           # ← Present here
    "OTHER": "content_filter",              # ← Present here
    "BLOCKLIST": "content_filter",
    "PROHIBITED_CONTENT": "content_filter",
    "SPII": "content_filter",
    "IMAGE_SAFETY": "content_filter"
}
```

---

## Impact Analysis

### Scenario: Response with `finishReason="LANGUAGE"` or `finishReason="OTHER"`

#### Current Behavior (INCORRECT):

1. **Detection Phase** (Line 2186-2196 in `transform_response()`):
   ```python
   content_policy_violations = VertexGeminiConfig().get_flagged_finish_reasons()
   if _candidates[0]["finishReason"] in content_policy_violations.keys():
       return self._handle_content_policy_violation(...)
   ```
   - ❌ `LANGUAGE` and `OTHER` are NOT in `content_policy_violations`
   - ❌ Check fails, continues to normal processing

2. **Processing Phase** (Line 2210-2216):
   - ✓ Calls `_process_candidates()`
   - ✓ Calls `_check_finish_reason()` which correctly maps to `content_filter`
   - ✓ Response has `finish_reason="content_filter"` in choices

3. **The Problem:**
   - Response content is NOT set to `None` (should be filtered)
   - Response is NOT handled by `_handle_content_policy_violation()`
   - Inconsistent with other content filter reasons (SAFETY, RECITATION, etc.)

#### Expected Behavior (CORRECT):

1. **Detection Phase:**
   - ✓ `LANGUAGE` and `OTHER` should be in `get_flagged_finish_reasons()`
   - ✓ Check succeeds, calls `_handle_content_policy_violation()`

2. **Handling Phase:**
   - ✓ Sets `finish_reason="content_filter"`
   - ✓ Sets `content=None` in message
   - ✓ Properly extracts usage metadata
   - ✓ Consistent with other content filter reasons

---

## Additional Inconsistency

### File: `litellm/litellm_core_utils/core_helpers.py` (Lines 87-95)

The `map_finish_reason()` function also doesn't include `LANGUAGE` or `OTHER`:

```python
elif finish_reason in (
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
    # Missing: "LANGUAGE", "OTHER"
):  # vertex ai / gemini
    return "content_filter"
```

This creates a third location where the mapping is incomplete.

---

## Root Cause

The `get_flagged_finish_reasons()` method was not updated when `LANGUAGE` and `OTHER` were added to `get_finish_reason_mapping()`. This creates an inconsistency where:

- `get_finish_reason_mapping()` knows these are content filters
- `get_flagged_finish_reasons()` doesn't recognize them as policy violations
- `map_finish_reason()` in core_helpers.py also doesn't recognize them

---

## Recommended Fixes

### Fix 1: Update `get_flagged_finish_reasons()` in vertex_and_google_ai_studio_gemini.py

**Location:** Line 1186-1200

**Change:**
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
        "LANGUAGE": "The token generation was stopped as the response was flagged for language-related content filtering.",  # ADD
        "OTHER": "The token generation was stopped for other content filtering reasons.",  # ADD
    }
```

### Fix 2: Update `map_finish_reason()` in litellm_core_utils/core_helpers.py

**Location:** Line 87-95

**Change:**
```python
elif finish_reason in (
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
    "LANGUAGE",  # ADD
    "OTHER",     # ADD
):  # vertex ai / gemini
    return "content_filter"
```

---

## Test Coverage

### Existing Test (Should Catch This)

**File:** `tests/test_litellm/llms/vertex_ai/gemini/test_vertex_and_google_ai_studio_gemini.py`  
**Test:** `test_all_flagged_finish_reasons_in_mapping()` (Line 631)

This test checks if all flagged reasons are in the mapping, but it doesn't check the reverse (if all content_filter mappings are in flagged reasons).

### Recommended Additional Test

```python
def test_all_content_filter_mappings_are_flagged():
    """
    Test that all finish reasons mapped to 'content_filter' are also 
    present in the flagged finish reasons (except for special cases).
    """
    flagged = VertexGeminiConfig().get_flagged_finish_reasons()
    mapping = VertexGeminiConfig.get_finish_reason_mapping()
    
    for reason, mapped_value in mapping.items():
        if mapped_value == "content_filter":
            assert reason in flagged, \
                f"{reason} maps to 'content_filter' but is not in flagged finish reasons"
```

---

## Verification Steps

After applying the fixes:

1. Run existing tests:
   ```bash
   pytest tests/test_litellm/llms/vertex_ai/gemini/test_vertex_and_google_ai_studio_gemini.py::test_all_flagged_finish_reasons_in_mapping -xvs
   ```

2. Test with actual responses containing `LANGUAGE` or `OTHER` finish reasons

3. Verify that responses are properly filtered (content set to None)

---

## Conclusion

**The mismatch exists and causes incorrect handling of content-filtered responses.**

- `LANGUAGE` and `OTHER` finish reasons are mapped to `content_filter` but not flagged as policy violations
- This causes responses with these finish reasons to bypass the content filtering logic
- The fix is straightforward: add these two finish reasons to `get_flagged_finish_reasons()` and `map_finish_reason()`
- This ensures consistent handling across all content filter scenarios
