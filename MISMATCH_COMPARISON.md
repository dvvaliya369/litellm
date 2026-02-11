# Content Filter Finish Reason - Side-by-Side Comparison

## Quick Visual Comparison

| Finish Reason | `get_flagged_finish_reasons()` | `get_finish_reason_mapping()` | `map_finish_reason()` (core_helpers.py) | Status |
|---------------|-------------------------------|-------------------------------|----------------------------------------|--------|
| SAFETY | ✅ Included | ✅ → content_filter | ✅ → content_filter | ✅ Consistent |
| RECITATION | ✅ Included | ✅ → content_filter | ✅ → content_filter | ✅ Consistent |
| BLOCKLIST | ✅ Included | ✅ → content_filter | ✅ → content_filter | ✅ Consistent |
| PROHIBITED_CONTENT | ✅ Included | ✅ → content_filter | ✅ → content_filter | ✅ Consistent |
| SPII | ✅ Included | ✅ → content_filter | ✅ → content_filter | ✅ Consistent |
| IMAGE_SAFETY | ✅ Included | ✅ → content_filter | ✅ → content_filter | ✅ Consistent |
| **LANGUAGE** | ❌ **MISSING** | ✅ → content_filter | ❌ **MISSING** | ❌ **INCONSISTENT** |
| **OTHER** | ❌ **MISSING** | ✅ → content_filter | ❌ **MISSING** | ❌ **INCONSISTENT** |

---

## Code Comparison

### Location 1: `get_flagged_finish_reasons()` 
**File:** `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py` (Lines 1186-1200)

```python
def get_flagged_finish_reasons(self) -> Dict[str, str]:
    return {
        "SAFETY": "...",
        "RECITATION": "...",
        "BLOCKLIST": "...",
        "PROHIBITED_CONTENT": "...",
        "SPII": "...",
        "IMAGE_SAFETY": "...",
        # ❌ MISSING: "LANGUAGE"
        # ❌ MISSING: "OTHER"
    }
```

### Location 2: `get_finish_reason_mapping()`
**File:** `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py` (Lines 1202-1220)

```python
def get_finish_reason_mapping() -> Dict[str, OpenAIChatCompletionFinishReason]:
    return {
        "FINISH_REASON_UNSPECIFIED": "finish_reason_unspecified",
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "LANGUAGE": "content_filter",           # ✅ Present
        "OTHER": "content_filter",              # ✅ Present
        "BLOCKLIST": "content_filter",
        "PROHIBITED_CONTENT": "content_filter",
        "SPII": "content_filter",
        "MALFORMED_FUNCTION_CALL": "malformed_function_call",
        "IMAGE_SAFETY": "content_filter",
    }
```

### Location 3: `map_finish_reason()`
**File:** `litellm/litellm_core_utils/core_helpers.py` (Lines 87-95)

```python
def map_finish_reason(finish_reason: str):
    # ... other mappings ...
    elif finish_reason in (
        "SAFETY",
        "RECITATION",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "IMAGE_SAFETY",
        # ❌ MISSING: "LANGUAGE"
        # ❌ MISSING: "OTHER"
    ):  # vertex ai / gemini
        return "content_filter"
    # ... other mappings ...
```

---

## Impact Flow Diagram

```
Response with finishReason="LANGUAGE" or "OTHER"
│
├─► transform_response() [Line 2186-2196]
│   │
│   ├─► get_flagged_finish_reasons()
│   │   └─► Returns: {SAFETY, RECITATION, BLOCKLIST, PROHIBITED_CONTENT, SPII, IMAGE_SAFETY}
│   │       ❌ LANGUAGE not in list
│   │       ❌ OTHER not in list
│   │
│   └─► Check: finishReason in content_policy_violations?
│       └─► ❌ FALSE - continues to normal processing
│           (Should have called _handle_content_policy_violation)
│
├─► _process_candidates() [Line 2210-2216]
│   │
│   └─► _check_finish_reason() [Line 1719-1733]
│       │
│       ├─► get_finish_reason_mapping()
│       │   └─► Returns: {..., "LANGUAGE": "content_filter", "OTHER": "content_filter", ...}
│       │       ✅ LANGUAGE found
│       │       ✅ OTHER found
│       │
│       └─► Returns: "content_filter"
│           ✅ Correct finish_reason in response
│
└─► RESULT:
    ✅ finish_reason = "content_filter" (correct)
    ❌ content = <actual content> (should be None)
    ❌ Not handled as content policy violation (inconsistent)
```

---

## What Should Happen vs What Actually Happens

### Scenario: Response with `finishReason="LANGUAGE"`

#### ❌ Current Behavior (WRONG)

1. `transform_response()` checks if "LANGUAGE" is in flagged reasons
2. "LANGUAGE" is NOT in `get_flagged_finish_reasons()`
3. Continues to normal processing
4. `_check_finish_reason()` maps "LANGUAGE" → "content_filter"
5. **Result:** 
   - ✅ `finish_reason="content_filter"` 
   - ❌ `content=<actual text>` (should be None)
   - ❌ Not handled by `_handle_content_policy_violation()`

#### ✅ Expected Behavior (CORRECT)

1. `transform_response()` checks if "LANGUAGE" is in flagged reasons
2. "LANGUAGE" IS in `get_flagged_finish_reasons()`
3. Calls `_handle_content_policy_violation()`
4. **Result:**
   - ✅ `finish_reason="content_filter"`
   - ✅ `content=None` (properly filtered)
   - ✅ Handled consistently with other content filters

---

## The Fix (Summary)

Add these two lines to **TWO** locations:

### 1. In `get_flagged_finish_reasons()`:
```python
"LANGUAGE": "The token generation was stopped as the response was flagged for language-related content filtering.",
"OTHER": "The token generation was stopped for other content filtering reasons.",
```

### 2. In `map_finish_reason()`:
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
):
    return "content_filter"
```

---

## Conclusion

**YES, there is a mismatch causing incorrect content filter handling.**

The issue is clear: `LANGUAGE` and `OTHER` are recognized as content filters in the mapping but not flagged as policy violations, causing them to bypass the proper content filtering logic.
