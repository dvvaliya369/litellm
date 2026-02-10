# TOOL_CALLS_CACHE Code Flow Trace

This document traces the complete flow of how `ChatCompletionMessageToolCall` objects are stored and retrieved from `TOOL_CALLS_CACHE`.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CACHE INITIALIZATION                                     │
│    File: transformation.py, Line 61                         │
│    TOOL_CALLS_CACHE = InMemoryCache()                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. CACHE STORAGE (Production)                               │
│    File: transformation.py, Line 1237                       │
│    Method: transform_chat_completion_tools_to_responses_tools│
│                                                              │
│    for tool_call in choice.message.tool_calls:              │
│        TOOL_CALLS_CACHE.set_cache(                          │
│            key=tool_call.id,                                │
│            value=tool_call  ← ChatCompletionMessageToolCall │
│        )                                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CACHE RETRIEVAL - Location 1                             │
│    File: transformation.py, Line 735                        │
│    Method: _ensure_tool_results_have_corresponding_tool_calls│
│                                                              │
│    _tool_use_definition = TOOL_CALLS_CACHE.get_cache(       │
│        key=tool_call_id                                     │
│    )  ← Returns ChatCompletionMessageToolCall               │
│                                                              │
│    if _tool_use_definition:                                 │
│        if not isinstance(_tool_use_definition, dict):       │
│            if hasattr(_tool_use_definition, "model_dump"):  │
│                _tool_use_definition = _tool_use_definition.model_dump()│
│            elif hasattr(_tool_use_definition, "dict"):      │
│                _tool_use_definition = _tool_use_definition.dict()│
│            else:                                             │
│                _tool_use_definition = {}                    │
│        # Now _tool_use_definition is a dict                 │
│        tool_call_chunk = _create_tool_call_chunk(...)       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. CACHE RETRIEVAL - Location 2                             │
│    File: transformation.py, Line 933                        │
│    Method: _transform_responses_api_tool_call_output_to_chat_completion_message│
│                                                              │
│    _tool_use_definition = TOOL_CALLS_CACHE.get_cache(       │
│        key=tool_call_output.get("call_id") or ""            │
│    )  ← Returns ChatCompletionMessageToolCall               │
│                                                              │
│    if _tool_use_definition:                                 │
│        if not isinstance(_tool_use_definition, dict):       │
│            if hasattr(_tool_use_definition, "model_dump"):  │
│                _tool_use_definition = _tool_use_definition.model_dump()│
│            elif hasattr(_tool_use_definition, "dict"):      │
│                _tool_use_definition = _tool_use_definition.dict()│
│            else:                                             │
│                _tool_use_definition = {}                    │
│        # Now _tool_use_definition is a dict                 │
│        function: dict = _tool_use_definition.get("function")│
│        tool_call_chunk = ChatCompletionToolCallChunk(...)   │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Code Trace

### Step 1: Cache Initialization

**File**: `litellm/responses/litellm_completion_transformation/transformation.py`  
**Line**: 61

```python
########### Initialize Classes used for Responses API  ###########
TOOL_CALLS_CACHE = InMemoryCache()
```

### Step 2: Cache Storage

**File**: `litellm/responses/litellm_completion_transformation/transformation.py`  
**Line**: 1237  
**Method**: `transform_chat_completion_tools_to_responses_tools`

```python
@staticmethod
def transform_chat_completion_tools_to_responses_tools(
    chat_completion_response: ModelResponse,
) -> List[ResponseFunctionToolCall]:
    all_chat_completion_tools: List[ChatCompletionMessageToolCall] = []
    for choice in chat_completion_response.choices:
        if isinstance(choice, Choices):
            if choice.message.tool_calls:
                all_chat_completion_tools.extend(choice.message.tool_calls)
                for tool_call in choice.message.tool_calls:
                    TOOL_CALLS_CACHE.set_cache(
                        key=tool_call.id,
                        value=tool_call,  # ← ChatCompletionMessageToolCall object
                    )
```

**What's Stored**: `ChatCompletionMessageToolCall` - a Pydantic model

**Structure of ChatCompletionMessageToolCall**:
```python
class ChatCompletionMessageToolCall(OpenAIObject):
    id: str                    # e.g., "toolu_0123456789abcdef"
    type: str                  # e.g., "function"
    function: Function         # Function object with name and arguments
    
    def get(self, key, default=None):
        return getattr(self, key, default)
```

### Step 3: Cache Retrieval - Location 1

**File**: `litellm/responses/litellm_completion_transformation/transformation.py`  
**Line**: 735  
**Method**: `_ensure_tool_results_have_corresponding_tool_calls`

```python
@staticmethod
def _ensure_tool_results_have_corresponding_tool_calls(
    messages: List[Union[AllMessageValues, GenericChatCompletionMessage, ChatCompletionResponseMessage]],
    tools: Optional[List[Any]] = None,
) -> List[Union[AllMessageValues, GenericChatCompletionMessage, ChatCompletionResponseMessage]]:
    # ... (earlier code)
    
    # Line 735: Cache retrieval
    if not LiteLLMCompletionResponsesConfig._check_tool_call_exists(
        tool_calls, tool_call_id
    ):
        _tool_use_definition = TOOL_CALLS_CACHE.get_cache(key=tool_call_id)
        # ↑ Returns ChatCompletionMessageToolCall (Pydantic model)
        
        if not _tool_use_definition and tools:
            _tool_use_definition = (
                LiteLLMCompletionResponsesConfig._reconstruct_tool_call_from_tools(
                    tool_call_id, tools
                )
            )
            # ↑ Returns Dict[str, Any] (plain dictionary)
        
        if _tool_use_definition:
            # Line 744: Conversion logic
            if not isinstance(_tool_use_definition, dict):
                if hasattr(_tool_use_definition, "model_dump"):
                    _tool_use_definition = _tool_use_definition.model_dump()
                elif hasattr(_tool_use_definition, "dict"):
                    _tool_use_definition = _tool_use_definition.dict()
                else:
                    _tool_use_definition = {}
            
            # Line 752: Create tool call chunk (expects dict)
            tool_call_chunk = (
                LiteLLMCompletionResponsesConfig._create_tool_call_chunk(
                    _tool_use_definition, tool_call_id, len(tool_calls)
                )
            )
            
            # Line 756: Add to assistant message
            LiteLLMCompletionResponsesConfig._add_tool_call_to_assistant(
                prev_assistant, tool_call_chunk
            )
```

**Key Points**:
- ✅ Checks if `_tool_use_definition` is a dict
- ✅ Converts Pydantic model to dict using `model_dump()` or `dict()`
- ✅ Only uses as dict after conversion

### Step 4: Cache Retrieval - Location 2

**File**: `litellm/responses/litellm_completion_transformation/transformation.py`  
**Line**: 933  
**Method**: `_transform_responses_api_tool_call_output_to_chat_completion_message`

```python
@staticmethod
def _transform_responses_api_tool_call_output_to_chat_completion_message(
    tool_call_output: Dict[str, Any],
) -> List[
    Union[
        AllMessageValues,
        GenericChatCompletionMessage,
        ChatCompletionResponseMessage,
    ]
]:
    # ... (earlier code for creating tool_output_message)
    
    # Line 933: Cache retrieval
    _tool_use_definition = TOOL_CALLS_CACHE.get_cache(
        key=tool_call_output.get("call_id") or "",
    )
    # ↑ Returns ChatCompletionMessageToolCall (Pydantic model)
    
    if _tool_use_definition:
        """
        Append the tool use definition to the list of messages
        
        Providers like Anthropic require the tool use definition to be 
        included with the tool output
        """
        # Line 960: Conversion logic
        if not isinstance(_tool_use_definition, dict):
            if hasattr(_tool_use_definition, "model_dump"):
                _tool_use_definition = _tool_use_definition.model_dump()
            elif hasattr(_tool_use_definition, "dict"):
                _tool_use_definition = _tool_use_definition.dict()
            else:
                _tool_use_definition = {}
        
        # Line 968: Use as dict
        function: dict = _tool_use_definition.get("function") or {}
        tool_call_chunk = ChatCompletionToolCallChunk(
            id=_tool_use_definition.get("id") or "",
            type=cast(Literal["function"], _tool_use_definition.get("type") or "function"),
            function=ChatCompletionToolCallFunctionChunk(
                name=function.get("name") or "",
                arguments=str(function.get("arguments") or ""),
            ),
            index=0,
        )
        
        # Line 978: Create response message
        chat_completion_response_message = ChatCompletionResponseMessage(
            tool_calls=[tool_call_chunk],
            role="assistant",
        )
        return [chat_completion_response_message, tool_output_message]
    
    return [tool_output_message]
```

**Key Points**:
- ✅ Checks if `_tool_use_definition` is a dict
- ✅ Converts Pydantic model to dict using `model_dump()` or `dict()`
- ✅ Only uses as dict after conversion

## Helper Method: `_create_tool_call_chunk`

**File**: `litellm/responses/litellm_completion_transformation/transformation.py`  
**Line**: 656

```python
@staticmethod
def _create_tool_call_chunk(
    tool_use_definition: Dict[str, Any],  # ← Type hint: expects dict
    tool_call_id: str, 
    index: int
) -> ChatCompletionToolCallChunk:
    """Create a ChatCompletionToolCallChunk from tool_use_definition."""
    function_raw = tool_use_definition.get("function")
    # ↑ Uses .get() - assumes dict
    
    function: Dict[str, Any] = function_raw if isinstance(function_raw, dict) else {}
    tool_use_id_raw = tool_use_definition.get("id")
    tool_use_id: str = (
        str(tool_use_id_raw) if tool_use_id_raw is not None else str(tool_call_id)
    )
    tool_use_type_raw = tool_use_definition.get("type")
    tool_use_type: str = (
        str(tool_use_type_raw) if tool_use_type_raw is not None else "function"
    )
    return ChatCompletionToolCallChunk(
        id=tool_use_id,
        type=cast(Literal["function"], tool_use_type),
        function=ChatCompletionToolCallFunctionChunk(
            name=str(function.get("name", "")),
            arguments=str(function.get("arguments", "{}")),
        ),
        index=index,
    )
```

**Key Points**:
- Type hint explicitly says `Dict[str, Any]`
- Uses `.get()` method throughout
- **Requires** a dictionary, not a Pydantic model

## Test Code: Cache Storage

**File**: `tests/llm_responses_api_testing/test_anthropic_tool_result_empty_call_id.py`  
**Line**: 133

```python
def test_tool_calls_added_when_missing():
    tool_call_id = "toolu_0123456789abcdef"
    
    # Cache the tool_call definition
    TOOL_CALLS_CACHE.set_cache(
        key=tool_call_id,
        value={  # ← Plain dictionary (different from production!)
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": "shell",
                "arguments": '{\"command\": [\"echo\", \"hello\"]}'
            }
        }
    )
```

**Difference**: Tests store **plain dictionaries**, production stores **Pydantic models**

## Summary of Findings

### ✅ Correct Behavior

Both cache retrieval locations (Line 735 and Line 933) properly handle Pydantic models:

1. Retrieve from cache (may be Pydantic model or dict)
2. Check if it's a dict
3. If not a dict, convert using `model_dump()` or `dict()`
4. Use as dictionary

### ⚠️ Code Quality Issues

1. **Code Duplication**: Conversion logic appears in 2 places
2. **Inconsistent Storage**: Production uses Pydantic models, tests use dicts
3. **Silent Fallback**: Empty dict fallback if conversion fails
4. **Type Ambiguity**: Cache can contain mixed types

### 📝 Conclusion

**The cache retrieval logic does NOT incorrectly assume cached entries are plain dictionaries.** The code properly checks and converts Pydantic models to dictionaries before use.

The question's premise is incorrect - there is no bug here, only code quality improvements that could be made.
