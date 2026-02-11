# Gemini finishReason Mismatch - Flow Diagrams

## Before Fix: Content Filter Bypass Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  User Request: Generate image with problematic content          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Gemini API Response                                             │
│  {                                                               │
│    "candidates": [{                                              │
│      "content": {                                                │
│        "parts": [{"inlineData": {"data": "base64..."}}]         │
│      },                                                          │
│      "finishReason": "LANGUAGE"  ◄── Language policy violation  │
│    }]                                                            │
│  }                                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  transform_image_generation_response()                           │
│                                                                  │
│  Step 1: Get flagged finish reasons                             │
│  content_policy_violations = get_flagged_finish_reasons()       │
│  ┌──────────────────────────────────────────────────┐           │
│  │ Returns: {                                       │           │
│  │   "SAFETY": "...",                               │           │
│  │   "RECITATION": "...",                           │           │
│  │   "BLOCKLIST": "...",                            │           │
│  │   "PROHIBITED_CONTENT": "...",                   │           │
│  │   "SPII": "...",                                 │           │
│  │   "IMAGE_SAFETY": "..."                          │           │
│  │   ❌ MISSING: "LANGUAGE"                         │           │
│  │   ❌ MISSING: "OTHER"                            │           │
│  │ }                                                │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  Step 2: Check if finishReason is flagged                       │
│  if finish_reason in content_policy_violations:                 │
│      ❌ "LANGUAGE" NOT in dict → Check returns FALSE            │
│                                                                  │
│  Step 3: ❌ BYPASS - Continue to normal processing              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Normal Processing (Should NOT happen for filtered content)     │
│                                                                  │
│  for candidate in candidates:                                   │
│      content = candidate.get("content", {})                     │
│      parts = content.get("parts", [])                           │
│      for part in parts:                                         │
│          if "inlineData" in part:                               │
│              ❌ EXTRACTS IMAGE DATA                             │
│              model_response.data.append(ImageObject(            │
│                  b64_json=inline_data["data"]  ◄── LEAKED!      │
│              ))                                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  ❌ RESULT: Content Filter Bypass                               │
│                                                                  │
│  Response returned to user:                                     │
│  {                                                               │
│    "data": [                                                     │
│      {                                                           │
│        "b64_json": "base64_image_data...",  ◄── SHOULD BE BLOCKED│
│        "url": null                                               │
│      }                                                           │
│    ],                                                            │
│    "finish_reason": "content_filter"  ◄── Mapped correctly      │
│  }                                                               │
│                                                                  │
│  ⚠️  SECURITY ISSUE: finish_reason says "content_filter"        │
│      but image data is still present!                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## After Fix: Proper Content Filtering Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  User Request: Generate image with problematic content          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Gemini API Response                                             │
│  {                                                               │
│    "candidates": [{                                              │
│      "content": {                                                │
│        "parts": [{"inlineData": {"data": "base64..."}}]         │
│      },                                                          │
│      "finishReason": "LANGUAGE"  ◄── Language policy violation  │
│    }]                                                            │
│  }                                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  transform_image_generation_response()                           │
│                                                                  │
│  Step 1: Get flagged finish reasons                             │
│  content_policy_violations = get_flagged_finish_reasons()       │
│  ┌──────────────────────────────────────────────────┐           │
│  │ Returns: {                                       │           │
│  │   "SAFETY": "...",                               │           │
│  │   "RECITATION": "...",                           │           │
│  │   "BLOCKLIST": "...",                            │           │
│  │   "PROHIBITED_CONTENT": "...",                   │           │
│  │   "SPII": "...",                                 │           │
│  │   "IMAGE_SAFETY": "...",                         │           │
│  │   ✅ "LANGUAGE": "language-related violations"   │           │
│  │   ✅ "OTHER": "other filtering reasons"          │           │
│  │ }                                                │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  Step 2: Check if finishReason is flagged                       │
│  if finish_reason in content_policy_violations:                 │
│      ✅ "LANGUAGE" IS in dict → Check returns TRUE              │
│                                                                  │
│  Step 3: ✅ DETECTED - Raise content filter error               │
│  error_message = content_policy_violations[finish_reason]       │
│  raise self.get_error_class(                                    │
│      error_message=f"Content policy violation: {error_message}" │
│      status_code=400                                            │
│  )                                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  ✅ RESULT: Proper Content Filtering                            │
│                                                                  │
│  Exception raised to user:                                      │
│  {                                                               │
│    "error": {                                                    │
│      "message": "Content policy violation: The token            │
│                  generation was stopped as the response was     │
│                  flagged for language-related content policy    │
│                  violations. finish_reason: LANGUAGE",          │
│      "type": "BadRequestError",                                 │
│      "code": 400                                                │
│    }                                                             │
│  }                                                               │
│                                                                  │
│  ✅ NO IMAGE DATA LEAKED                                        │
│  ✅ CLEAR ERROR MESSAGE                                         │
│  ✅ PROPER SECURITY ENFORCEMENT                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Three Validation Points

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Gemini finishReason Processing                        │
│                                                                          │
│  finishReason from Gemini API: "LANGUAGE" or "OTHER"                    │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌────────────────┐   ┌──────────────────┐
│ Validation #1 │   │ Validation #2  │   │  Validation #3   │
│               │   │                │   │                  │
│ get_flagged_  │   │ get_finish_    │   │ map_finish_      │
│ finish_       │   │ reason_        │   │ reason()         │
│ reasons()     │   │ mapping()      │   │ (core_helpers)   │
│               │   │                │   │                  │
│ Purpose:      │   │ Purpose:       │   │ Purpose:         │
│ Detect policy │   │ Map Gemini →   │   │ Global finish    │
│ violations    │   │ OpenAI format  │   │ reason mapper    │
│               │   │                │   │                  │
│ Used by:      │   │ Used by:       │   │ Used by:         │
│ - Image gen   │   │ - Chat         │   │ - All providers  │
│ - Image edit  │   │ - Streaming    │   │ - Streaming      │
│ - Chat        │   │ - Batch        │   │ - Batch          │
│               │   │                │   │                  │
│ BEFORE:       │   │ BEFORE:        │   │ BEFORE:          │
│ ❌ Missing    │   │ ✅ Had         │   │ ❌ Missing       │
│   LANGUAGE    │   │   LANGUAGE     │   │   LANGUAGE       │
│ ❌ Missing    │   │ ✅ Had         │   │ ❌ Missing       │
│   OTHER       │   │   OTHER        │   │   OTHER          │
│               │   │                │   │                  │
│ AFTER:        │   │ AFTER:         │   │ AFTER:           │
│ ✅ Added      │   │ ✅ Already OK  │   │ ✅ Added         │
│   LANGUAGE    │   │   LANGUAGE     │   │   LANGUAGE       │
│ ✅ Added      │   │ ✅ Already OK  │   │ ✅ Added         │
│   OTHER       │   │   OTHER        │   │   OTHER          │
└───────────────┘   └────────────────┘   └──────────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │  ✅ ALL THREE NOW SYNCHRONIZED         │
        │                                        │
        │  Result: Consistent content filtering  │
        │  across all response types and code    │
        │  paths                                 │
        └────────────────────────────────────────┘
```

---

## Response Type Comparison

### Image Generation Response Processing

```
┌─────────────────────────────────────────────────────────────┐
│  File: litellm/llms/gemini/image_generation/transformation.py│
│  Method: transform_image_generation_response()              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │ Extract candidates from        │
        │ response_data                  │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Get flagged finish reasons     │
        │ content_policy_violations =    │
        │   get_flagged_finish_reasons() │
        │                                │
        │ ✅ NOW includes LANGUAGE/OTHER │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Check if finishReason flagged  │
        │ if finish_reason in            │
        │    content_policy_violations:  │
        │                                │
        │ ✅ NOW detects LANGUAGE/OTHER  │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Raise content filter error     │
        │ ✅ Blocks image data           │
        └────────────────────────────────┘
```

### Image Edit Response Processing

```
┌─────────────────────────────────────────────────────────────┐
│  File: litellm/llms/gemini/image_edit/transformation.py     │
│  Method: transform_image_edit_response()                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │ Extract candidates from        │
        │ response_json                  │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Get flagged finish reasons     │
        │ content_policy_violations =    │
        │   get_flagged_finish_reasons() │
        │                                │
        │ ✅ NOW includes LANGUAGE/OTHER │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Check if finishReason flagged  │
        │ if finish_reason in            │
        │    content_policy_violations:  │
        │                                │
        │ ✅ NOW detects LANGUAGE/OTHER  │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Raise content filter error     │
        │ ✅ Blocks edited image data    │
        └────────────────────────────────┘
```

### Chat Completion Response Processing

```
┌─────────────────────────────────────────────────────────────┐
│  File: litellm/llms/vertex_ai/gemini/                       │
│        vertex_and_google_ai_studio_gemini.py                │
│  Method: transform_response()                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │ Extract candidates from        │
        │ completion_response            │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Get flagged finish reasons     │
        │ content_policy_violations =    │
        │   get_flagged_finish_reasons() │
        │                                │
        │ ✅ NOW includes LANGUAGE/OTHER │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Check if finishReason flagged  │
        │ if finishReason in             │
        │    content_policy_violations:  │
        │                                │
        │ ✅ NOW detects LANGUAGE/OTHER  │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Call handler                   │
        │ _handle_content_policy_        │
        │ violation()                    │
        │                                │
        │ ✅ Sets content=None           │
        │ ✅ Sets finish_reason          │
        │ ✅ Extracts usage metadata     │
        └────────────────────────────────┘
```

---

## Key Insight: Why Image Generation Was Most Affected

```
┌──────────────────────────────────────────────────────────────────┐
│                    Content Filter Strictness                      │
│                                                                   │
│  Text Generation          Image Generation                       │
│  ┌──────────────┐         ┌──────────────┐                       │
│  │ SAFETY       │         │ SAFETY       │                       │
│  │ RECITATION   │         │ RECITATION   │                       │
│  │ BLOCKLIST    │         │ BLOCKLIST    │                       │
│  │ PROHIBITED   │         │ PROHIBITED   │                       │
│  │ SPII         │         │ SPII         │                       │
│  │              │         │ IMAGE_SAFETY │ ◄── Image-specific    │
│  │              │         │ LANGUAGE     │ ◄── More common in    │
│  │              │         │              │     image prompts     │
│  │              │         │ OTHER        │ ◄── More edge cases   │
│  └──────────────┘         └──────────────┘                       │
│                                                                   │
│  Frequency of LANGUAGE/OTHER:                                    │
│  Text:  ▓░░░░ (Low)                                              │
│  Image: ▓▓▓▓▓ (High)                                             │
│                                                                   │
│  Impact of bypass:                                               │
│  Text:  Filtered text leaked → Bad                              │
│  Image: Filtered image leaked → WORSE (visual content)          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Summary

The finishReason mismatch was caused by **parsing inconsistencies** across three validation points:

1. ❌ **`get_flagged_finish_reasons()`** - Missing LANGUAGE/OTHER
2. ✅ **`get_finish_reason_mapping()`** - Already had LANGUAGE/OTHER
3. ❌ **`map_finish_reason()`** - Missing LANGUAGE/OTHER

This created a **bypass** where:
- Finish reasons were **mapped** correctly (point #2)
- But **not detected** as violations (points #1 and #3)
- Different response types (image gen, image edit, chat) all failed the same way

The fix **synchronized all three points** to ensure consistent content filtering across all response types and code paths.
