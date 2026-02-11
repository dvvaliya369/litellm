# Answer: Content Filter Finish Reason Handling

## TL;DR

**YES, there is a mismatch.** Two finish reasons (`LANGUAGE` and `OTHER`) are being handled incorrectly:

- ✅ They are mapped to `content_filter` in `get_finish_reason_mapping()`
- ❌ They are NOT included in `get_flagged_finish_reasons()`
- ❌ They are NOT included in `map_finish_reason()` in core_helpers.py

This causes responses with these finish reasons to bypass content filtering logic.

---

## The Problem

### Three locations define content filter finish reasons:

1. **`get_flagged_finish_reasons()`** - Detects content policy violations
   - Has: SAFETY, RECITATION, BLOCKLIST, PROHIBITED_CONTENT, SPII, IMAGE_SAFETY
   - **Missing: LANGUAGE, OTHER**

2. **`get_finish_reason_mapping()`** - Maps to OpenAI format
   - Has: SAFETY, RECITATION, BLOCKLIST, PROHIBITED_CONTENT, SPII, IMAGE_SAFETY, **LANGUAGE, OTHER**
   - **Includes: LANGUAGE, OTHER** ✅

3. **`map_finish_reason()`** in core_helpers.py - Global mapping
   - Has: SAFETY, RECITATION, BLOCKLIST, PROHIBITED_CONTENT, SPII, IMAGE_SAFETY
   - **Missing: LANGUAGE, OTHER**

---

## What's Causing the Mismatch

When a response has `finishReason="LANGUAGE"` or `finishReason="OTHER"`:

### Current Flow (INCORRECT):
```
1. transform_response() checks: Is "LANGUAGE" in get_flagged_finish_reasons()?
   → NO (it's missing)
   → Continues to normal processing (WRONG - should call _handle_content_policy_violation)

2. _process_candidates() → _check_finish_reason()
   → Checks get_finish_reason_mapping()
   → Finds "LANGUAGE": "content_filter"
   → Returns "content_filter" (CORRECT)

3. Result:
   ✅ finish_reason = "content_filter" (correct)
   ❌ content = <actual text> (WRONG - should be None)
   ❌ Not handled as content policy violation (WRONG - inconsistent)
```

### Expected Flow (CORRECT):
```
1. transform_response() checks: Is "LANGUAGE" in get_flagged_finish_reasons()?
   → YES (after fix)
   → Calls _handle_content_policy_violation() (CORRECT)

2. _handle_content_policy_violation()
   → Sets finish_reason = "content_filter"
   → Sets content = None (properly filtered)
   → Extracts usage metadata

3. Result:
   ✅ finish_reason = "content_filter"
   ✅ content = None (properly filtered)
   ✅ Handled consistently with other content filters
```

---

## Impact

Responses with `finishReason="LANGUAGE"` or `finishReason="OTHER"`:
- ❌ Are NOT detected as content policy violations
- ❌ May include filtered content (content not set to None)
- ❌ Bypass `_handle_content_policy_violation()` logic
- ✅ Do get `finish_reason="content_filter"` (but through wrong path)

This creates **inconsistent behavior** compared to other content filter reasons like SAFETY, RECITATION, etc.

---

## The Fix

Add `LANGUAGE` and `OTHER` to two locations:

### Fix 1: `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py`

**Line 1186-1200** in `get_flagged_finish_reasons()`:

```python
def get_flagged_finish_reasons(self) -> Dict[str, str]:
    return {
        "SAFETY": "...",
        "RECITATION": "...",
        "BLOCKLIST": "...",
        "PROHIBITED_CONTENT": "...",
        "SPII": "...",
        "IMAGE_SAFETY": "...",
        "LANGUAGE": "The token generation was stopped as the response was flagged for language-related content filtering.",  # ADD
        "OTHER": "The token generation was stopped for other content filtering reasons.",  # ADD
    }
```

### Fix 2: `litellm/litellm_core_utils/core_helpers.py`

**Line 87-95** in `map_finish_reason()`:

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

## Files to Review

1. **Main issue:** `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py`
   - Line 1186-1200: `get_flagged_finish_reasons()` - Missing LANGUAGE and OTHER
   - Line 1202-1220: `get_finish_reason_mapping()` - Has LANGUAGE and OTHER ✅
   - Line 2186-2196: `transform_response()` - Uses get_flagged_finish_reasons() for detection

2. **Secondary issue:** `litellm/litellm_core_utils/core_helpers.py`
   - Line 87-95: `map_finish_reason()` - Missing LANGUAGE and OTHER

---

## Detailed Analysis Documents

I've created three detailed analysis documents:

1. **`CONTENT_FILTER_ISSUE_REPORT.md`** - Complete technical analysis
2. **`MISMATCH_COMPARISON.md`** - Side-by-side comparison with visual tables
3. **`content_filter_analysis.md`** - Initial analysis with code flow

---

## Conclusion

The mismatch is real and causes incorrect handling of content-filtered responses. The fix is straightforward: add `LANGUAGE` and `OTHER` to the two locations where they're missing to ensure consistent content filtering behavior across all finish reasons.
