# Gemini finishReason Mismatch - Code Examples

## The Problem in Code

### Example 1: Image Generation Response Parsing

**File:** `litellm/llms/gemini/image_generation/transformation.py`

#### BEFORE FIX (Lines 254-264):

```python
# Check for content policy violations via finishReason
content_policy_violations = (
    VertexGeminiConfig().get_flagged_finish_reasons()
)
if candidates and len(candidates) > 0:
    finish_reason = candidates[0].get("finishReason", "")
    if finish_reason in content_policy_violations:  # ❌ LANGUAGE/OTHER not in dict
        error_message = content_policy_violations[finish_reason]
        raise self.get_error_class(
            error_message=f"Content policy violation: {error_message}. finish_reason: {finish_reason}",
            status_code=400,
            headers=raw_response.headers,
        )

# ❌ If finishReason="LANGUAGE", code continues here and extracts image data
for candidate in candidates:
    content = candidate.get("content", {})
    parts = content.get("parts", [])
    for part in parts:
        if "inlineData" in part:
            inline_data = part["inlineData"]
            if "data" in inline_data:
                # ❌ IMAGE DATA LEAKED - Should have been blocked above
                model_response.data.append(ImageObject(
                    b64_json=inline_data["data"],
                    url=None,
                ))
```

**What happens with finishReason="LANGUAGE":**
1. `get_flagged_finish_reasons()` returns dict WITHOUT "LANGUAGE"
2. Check `if finish_reason in content_policy_violations` returns **False**
3. Code continues to extract image data
4. Image data is returned to user even though it should be blocked

#### AFTER FIX:

```python
# Check for content policy violations via finishReason
content_policy_violations = (
    VertexGeminiConfig().get_flagged_finish_reasons()  # ✅ NOW includes LANGUAGE/OTHER
)
if candidates and len(candidates) > 0:
    finish_reason = candidates[0].get("finishReason", "")
    if finish_reason in content_policy_violations:  # ✅ LANGUAGE/OTHER now detected
        error_message = content_policy_violations[finish_reason]
        raise self.get_error_class(
            error_message=f"Content policy violation: {error_message}. finish_reason: {finish_reason}",
            status_code=400,
            headers=raw_response.headers,
        )

# ✅ Code never reaches here for LANGUAGE/OTHER - exception raised above
```

**What happens with finishReason="LANGUAGE" after fix:**
1. `get_flagged_finish_reasons()` returns dict WITH "LANGUAGE"
2. Check `if finish_reason in content_policy_violations` returns **True**
3. Exception is raised immediately
4. No image data is extracted or returned

---

### Example 2: The Missing Entries in get_flagged_finish_reasons()

**File:** `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py`

#### BEFORE FIX (Lines 1186-1200):

```python
def get_flagged_finish_reasons(self) -> Dict[str, str]:
    """
    Return Dictionary of finish reasons which indicate response was flagged
    and what it means
    """
    return {
        "SAFETY": "The token generation was stopped as the response was flagged for safety reasons...",
        "RECITATION": "The token generation was stopped as the response was flagged for unauthorized citations.",
        "BLOCKLIST": "The token generation was stopped as the response was flagged for the terms which are included from the terminology blocklist.",
        "PROHIBITED_CONTENT": "The token generation was stopped as the response was flagged for the prohibited contents.",
        "SPII": "The token generation was stopped as the response was flagged for Sensitive Personally Identifiable Information (SPII) contents.",
        "IMAGE_SAFETY": "The token generation was stopped as the response was flagged for image safety reasons.",
        # ❌ MISSING: "LANGUAGE"
        # ❌ MISSING: "OTHER"
    }
```

**Problem:** When code checks `if "LANGUAGE" in get_flagged_finish_reasons()`, it returns **False**.

#### AFTER FIX (Lines 1186-1200):

```python
def get_flagged_finish_reasons(self) -> Dict[str, str]:
    """
    Return Dictionary of finish reasons which indicate response was flagged
    and what it means
    """
    return {
        "SAFETY": "The token generation was stopped as the response was flagged for safety reasons...",
        "RECITATION": "The token generation was stopped as the response was flagged for unauthorized citations.",
        "BLOCKLIST": "The token generation was stopped as the response was flagged for the terms which are included from the terminology blocklist.",
        "PROHIBITED_CONTENT": "The token generation was stopped as the response was flagged for the prohibited contents.",
        "SPII": "The token generation was stopped as the response was flagged for Sensitive Personally Identifiable Information (SPII) contents.",
        "IMAGE_SAFETY": "The token generation was stopped as the response was flagged for image safety reasons.",
        "LANGUAGE": "The token generation was stopped as the response was flagged for language-related content policy violations.",  # ✅ ADDED
        "OTHER": "The token generation was stopped for other content filtering reasons, including unexpected safety violations or backend moderation.",  # ✅ ADDED
    }
```

**Solution:** Now when code checks `if "LANGUAGE" in get_flagged_finish_reasons()`, it returns **True**.

---

### Example 3: The Inconsistency with get_finish_reason_mapping()

**File:** `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py`

#### This was ALREADY CORRECT (Lines 1204-1220):

```python
@staticmethod
def get_finish_reason_mapping() -> Dict[str, OpenAIChatCompletionFinishReason]:
    """
    Return Dictionary of finish reasons which indicate response was flagged
    and what it means
    """
    return {
        "FINISH_REASON_UNSPECIFIED": "finish_reason_unspecified",
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "LANGUAGE": "content_filter",  # ✅ Already present
        "OTHER": "content_filter",     # ✅ Already present
        "BLOCKLIST": "content_filter",
        "PROHIBITED_CONTENT": "content_filter",
        "SPII": "content_filter",
        "MALFORMED_FUNCTION_CALL": "malformed_function_call",
        "IMAGE_SAFETY": "content_filter",
    }
```

**The Inconsistency:**
- `get_finish_reason_mapping()` **HAD** LANGUAGE and OTHER ✅
- `get_flagged_finish_reasons()` **DID NOT HAVE** LANGUAGE and OTHER ❌

This meant:
- Finish reasons were **mapped** to "content_filter" correctly
- But **not detected** as violations in the validation step
- Result: Response has `finish_reason="content_filter"` but content is not blocked

---

### Example 4: The Missing Entries in map_finish_reason()

**File:** `litellm/litellm_core_utils/core_helpers.py`

#### BEFORE FIX (Lines 87-95):

```python
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
```

**Problem:** This function is used **globally** across the codebase. Without LANGUAGE/OTHER, some code paths would not recognize them as content filters.

#### AFTER FIX (Lines 87-95):

```python
elif finish_reason in (
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
    "LANGUAGE",  # ✅ ADDED
    "OTHER",     # ✅ ADDED
):  # vertex ai / gemini
    return "content_filter"
```

**Solution:** Now all code paths consistently recognize LANGUAGE/OTHER as content filters.

---

### Example 5: Chat Completion Response Parsing

**File:** `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py`

#### BEFORE FIX (Lines 2190-2199):

```python
_candidates = completion_response.get("candidates")
if _candidates and len(_candidates) > 0:
    content_policy_violations = (
        VertexGeminiConfig().get_flagged_finish_reasons()  # ❌ Missing LANGUAGE/OTHER
    )
    if (
        "finishReason" in _candidates[0]
        and _candidates[0]["finishReason"] in content_policy_violations.keys()  # ❌ Check fails
    ):
        return self._handle_content_policy_violation(
            model_response=model_response,
            completion_response=completion_response,
        )

# ❌ If finishReason="LANGUAGE", code continues here
# Response will have finish_reason="content_filter" (from mapping)
# But content is NOT set to None (because _handle_content_policy_violation was not called)
```

**What happens with finishReason="LANGUAGE":**
1. Check fails because LANGUAGE not in `get_flagged_finish_reasons()`
2. `_handle_content_policy_violation()` is **not called**
3. Content is **not cleared**
4. Response has `finish_reason="content_filter"` but content is still present

#### AFTER FIX:

```python
_candidates = completion_response.get("candidates")
if _candidates and len(_candidates) > 0:
    content_policy_violations = (
        VertexGeminiConfig().get_flagged_finish_reasons()  # ✅ Now includes LANGUAGE/OTHER
    )
    if (
        "finishReason" in _candidates[0]
        and _candidates[0]["finishReason"] in content_policy_violations.keys()  # ✅ Check succeeds
    ):
        return self._handle_content_policy_violation(  # ✅ Called
            model_response=model_response,
            completion_response=completion_response,
        )
```

**What happens with finishReason="LANGUAGE" after fix:**
1. Check succeeds because LANGUAGE is in `get_flagged_finish_reasons()`
2. `_handle_content_policy_violation()` **is called**
3. Content **is cleared** (set to None)
4. Response has `finish_reason="content_filter"` and content is properly blocked

---

### Example 6: The _handle_content_policy_violation() Method

**File:** `litellm/llms/vertex_ai/gemini/vertex_and_google_ai_studio_gemini.py`

This method is what **should** be called for content policy violations:

```python
def _handle_content_policy_violation(
    self,
    model_response: ModelResponse,
    completion_response: dict,
) -> ModelResponse:
    """
    Handle content policy violations by:
    1. Setting finish_reason to "content_filter"
    2. Setting content to None
    3. Extracting usage metadata
    """
    # Set finish reason
    model_response.choices = [
        Choices(
            finish_reason="content_filter",
            index=0,
            message=Message(
                content=None,  # ✅ Content is cleared
                role="assistant",
            ),
        )
    ]
    
    # Extract usage metadata
    usage = VertexGeminiConfig._calculate_usage(
        completion_response=completion_response
    )
    setattr(model_response, "usage", usage)
    
    return model_response
```

**Before fix:** This method was **not called** for LANGUAGE/OTHER finish reasons.  
**After fix:** This method **is called** for LANGUAGE/OTHER finish reasons.

---

## Real-World Scenarios

### Scenario 1: Image Generation with Language Violation

**User Request:**
```python
import litellm

response = litellm.image_generation(
    model="gemini/gemini-2.5-flash-image-preview",
    prompt="Generate an image with [harmful content in non-English language]"
)
```

**Gemini API Response:**
```json
{
  "candidates": [{
    "content": {
      "parts": [{
        "inlineData": {
          "data": "iVBORw0KGgoAAAANSUhEUgAA...",
          "mimeType": "image/png"
        }
      }]
    },
    "finishReason": "LANGUAGE"
  }]
}
```

**BEFORE FIX:**
```python
# Response returned to user:
{
  "data": [{
    "b64_json": "iVBORw0KGgoAAAANSUhEUgAA...",  # ❌ IMAGE DATA LEAKED
    "url": None
  }]
}
```

**AFTER FIX:**
```python
# Exception raised:
BadRequestError: Content policy violation: The token generation was stopped 
as the response was flagged for language-related content policy violations. 
finish_reason: LANGUAGE
```

---

### Scenario 2: Image Edit with OTHER Finish Reason

**User Request:**
```python
import litellm

response = litellm.image_edit(
    model="gemini/gemini-2.5-flash-image-preview",
    image=open("image.png", "rb"),
    prompt="Edit this image to show [edge case that triggers backend safety check]"
)
```

**Gemini API Response:**
```json
{
  "candidates": [{
    "content": {
      "parts": [{
        "inlineData": {
          "data": "iVBORw0KGgoAAAANSUhEUgAA...",
          "mimeType": "image/png"
        }
      }]
    },
    "finishReason": "OTHER"
  }]
}
```

**BEFORE FIX:**
```python
# Response returned to user:
{
  "data": [{
    "b64_json": "iVBORw0KGgoAAAANSUhEUgAA...",  # ❌ EDITED IMAGE DATA LEAKED
    "url": None
  }]
}
```

**AFTER FIX:**
```python
# Exception raised:
BadRequestError: Content policy violation: The token generation was stopped 
for other content filtering reasons, including unexpected safety violations 
or backend moderation. finish_reason: OTHER
```

---

### Scenario 3: Chat Completion with LANGUAGE Finish Reason

**User Request:**
```python
import litellm

response = litellm.completion(
    model="gemini/gemini-2.0-flash-exp",
    messages=[{"role": "user", "content": "[harmful content in specific language]"}]
)
```

**Gemini API Response:**
```json
{
  "candidates": [{
    "content": {
      "parts": [{
        "text": "I cannot provide that content."
      }],
      "role": "model"
    },
    "finishReason": "LANGUAGE"
  }]
}
```

**BEFORE FIX:**
```python
# Response returned to user:
{
  "choices": [{
    "message": {
      "content": "I cannot provide that content.",  # ❌ CONTENT PRESENT
      "role": "assistant"
    },
    "finish_reason": "content_filter"  # ✅ Mapped correctly but content leaked
  }]
}
```

**AFTER FIX:**
```python
# Response returned to user:
{
  "choices": [{
    "message": {
      "content": None,  # ✅ CONTENT PROPERLY CLEARED
      "role": "assistant"
    },
    "finish_reason": "content_filter"  # ✅ Mapped correctly and content blocked
  }]
}
```

---

## The Test That Prevents Regression

**File:** `tests/test_litellm/llms/vertex_ai/gemini/test_vertex_and_google_ai_studio_gemini.py`

```python
def test_all_content_filter_mappings_are_flagged():
    """
    Test that all finish reasons mapped to 'content_filter' are also 
    present in the flagged finish reasons (reverse validation).
    
    This ensures consistency between get_finish_reason_mapping() and 
    get_flagged_finish_reasons() to prevent content filter bypass.
    
    Edge case: If a finish reason maps to 'content_filter' but is not
    in flagged reasons, responses with that finish reason will bypass
    _handle_content_policy_violation() and may return content that
    should be filtered (especially critical for image generation).
    """
    flagged = VertexGeminiConfig().get_flagged_finish_reasons()
    mapping = VertexGeminiConfig.get_finish_reason_mapping()
    
    for reason, mapped_value in mapping.items():
        if mapped_value == "content_filter":
            assert reason in flagged, \
                f"{reason} maps to 'content_filter' but is not in flagged finish reasons. " \
                f"This can cause content filter bypass where responses are marked as filtered " \
                f"but content is not properly blocked. This is especially critical for image " \
                f"generation where LANGUAGE and OTHER finish reasons may occur."
```

**What this test does:**
1. Gets all finish reasons from `get_flagged_finish_reasons()`
2. Gets all finish reasons from `get_finish_reason_mapping()`
3. For each finish reason that maps to "content_filter":
   - Asserts it's also in the flagged finish reasons
4. If assertion fails, provides detailed error message

**Why this is important:**
- Prevents future additions to `get_finish_reason_mapping()` without updating `get_flagged_finish_reasons()`
- Catches the exact issue that caused the LANGUAGE/OTHER bypass
- Documents the expected behavior in code

---

## Summary

The finishReason mismatch was caused by **parsing logic inconsistencies** in three locations:

1. **`get_flagged_finish_reasons()`** - Used by image generation, image edit, and chat to detect violations
2. **`get_finish_reason_mapping()`** - Used to map Gemini finish reasons to OpenAI format
3. **`map_finish_reason()`** - Global finish reason mapper used across all providers

LANGUAGE and OTHER were:
- ✅ Present in `get_finish_reason_mapping()` (mapping worked)
- ❌ Missing from `get_flagged_finish_reasons()` (detection failed)
- ❌ Missing from `map_finish_reason()` (global mapping failed)

This caused:
- Image generation to leak filtered image data
- Image edit to leak filtered edited image data
- Chat completions to leak filtered text content

The fix synchronized all three locations to ensure consistent content filtering across all response types.
