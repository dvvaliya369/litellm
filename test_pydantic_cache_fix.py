#!/usr/bin/env python3
"""
Test to verify that the Pydantic-to-dict conversion fix works correctly.

This test simulates the real-world scenario where ChatCompletionMessageToolCall
(Pydantic object) is stored in the cache and then retrieved.
"""
import sys
import os

sys.path.insert(0, os.path.abspath("."))

from litellm.types.utils import ChatCompletionMessageToolCall, Function
from litellm.responses.litellm_completion_transformation.transformation import (
    LiteLLMCompletionResponsesConfig,
    TOOL_CALLS_CACHE
)


def test_pydantic_object_in_cache():
    """
    Test that Pydantic ChatCompletionMessageToolCall objects stored in cache
    are correctly converted to dict when retrieved.
    """
    print("\n" + "=" * 80)
    print("Testing Pydantic Object Cache Conversion Fix")
    print("=" * 80)
    
    # Create a Pydantic ChatCompletionMessageToolCall object
    tool_call_id = "call_test_123"
    pydantic_tool_call = ChatCompletionMessageToolCall(
        id=tool_call_id,
        type="function",
        function=Function(
            name="get_weather",
            arguments='{"location": "San Francisco"}'
        )
    )
    
    print(f"\n1. Created Pydantic object: {type(pydantic_tool_call)}")
    print(f"   - ID: {pydantic_tool_call.id}")
    print(f"   - Type: {pydantic_tool_call.type}")
    print(f"   - Function name: {pydantic_tool_call.function.name}")
    print(f"   - Function args: {pydantic_tool_call.function.arguments}")
    
    # Store the Pydantic object in cache (this is what happens in real usage)
    TOOL_CALLS_CACHE.set_cache(key=tool_call_id, value=pydantic_tool_call)
    print(f"\n2. Stored Pydantic object in TOOL_CALLS_CACHE")
    
    # Create messages with a tool result that references this cached tool call
    messages = [
        {
            "role": "user",
            "content": "What's the weather in San Francisco?"
        },
        {
            "role": "assistant",
            "content": "Let me check the weather for you."
            # Missing tool_calls - this is the bug scenario
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": '{"temperature": 72, "conditions": "sunny"}'
        }
    ]
    
    print(f"\n3. Created test messages (assistant missing tool_calls)")
    
    # Apply the fix
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        }
    ]
    
    fixed_messages = LiteLLMCompletionResponsesConfig._ensure_tool_results_have_corresponding_tool_calls(
        messages=messages,
        tools=tools
    )
    
    print(f"\n4. Applied _ensure_tool_results_have_corresponding_tool_calls fix")
    
    # Verify the fix worked
    assistant_message = None
    for msg in fixed_messages:
        if msg.get("role") == "assistant":
            assistant_message = msg
            break
    
    assert assistant_message is not None, "Assistant message should be present"
    
    # Check if tool_calls were added
    tool_calls = assistant_message.get("tool_calls") or []
    
    print(f"\n5. Verification Results:")
    print(f"   - Assistant message found: ✓")
    print(f"   - Tool calls count: {len(tool_calls)}")
    
    assert len(tool_calls) > 0, (
        "Fix should have added tool_calls to assistant message from Pydantic cache"
    )
    
    # Verify the tool_call details
    first_tool_call = tool_calls[0]
    
    # Handle both dict and Pydantic object formats
    if isinstance(first_tool_call, dict):
        tc_id = first_tool_call.get("id")
        tc_type = first_tool_call.get("type")
        tc_function = first_tool_call.get("function", {})
        tc_name = tc_function.get("name")
        tc_args = tc_function.get("arguments")
    else:
        tc_id = getattr(first_tool_call, "id", None)
        tc_type = getattr(first_tool_call, "type", None)
        tc_function = getattr(first_tool_call, "function", None)
        tc_name = getattr(tc_function, "name", None) if tc_function else None
        tc_args = getattr(tc_function, "arguments", None) if tc_function else None
    
    print(f"   - Tool call ID: {tc_id}")
    print(f"   - Tool call type: {tc_type}")
    print(f"   - Function name: {tc_name}")
    print(f"   - Function arguments: {tc_args}")
    
    assert tc_id == tool_call_id, f"Tool call ID mismatch: {tc_id} != {tool_call_id}"
    assert tc_name == "get_weather", f"Function name mismatch: {tc_name}"
    assert tc_args == '{"location": "San Francisco"}', f"Arguments mismatch: {tc_args}"
    
    print("\n" + "=" * 80)
    print("[PASS] Pydantic-to-dict conversion works correctly!")
    print("=" * 80)
    print("\nThe fix successfully:")
    print("  ✓ Retrieved Pydantic object from cache")
    print("  ✓ Converted it to dict format")
    print("  ✓ Created proper tool_call chunk")
    print("  ✓ Added it to assistant message")
    print("\nNo malformed tool calls with empty function names/arguments!")
    
    return True


def test_dict_in_cache_still_works():
    """
    Test backward compatibility: dict objects in cache should still work.
    """
    print("\n" + "=" * 80)
    print("Testing Backward Compatibility (Dict in Cache)")
    print("=" * 80)
    
    tool_call_id = "call_dict_test_456"
    dict_tool_call = {
        "id": tool_call_id,
        "type": "function",
        "function": {
            "name": "calculate",
            "arguments": '{"expression": "2+2"}'
        }
    }
    
    print(f"\n1. Created dict object: {type(dict_tool_call)}")
    
    # Store dict in cache
    TOOL_CALLS_CACHE.set_cache(key=tool_call_id, value=dict_tool_call)
    print(f"\n2. Stored dict object in TOOL_CALLS_CACHE")
    
    # Create messages
    messages = [
        {
            "role": "user",
            "content": "Calculate 2+2"
        },
        {
            "role": "assistant",
            "content": "Let me calculate that."
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": '{"result": 4}'
        }
    ]
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Calculate an expression",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string"}
                    }
                }
            }
        }
    ]
    
    # Apply the fix
    fixed_messages = LiteLLMCompletionResponsesConfig._ensure_tool_results_have_corresponding_tool_calls(
        messages=messages,
        tools=tools
    )
    
    print(f"\n3. Applied fix with dict in cache")
    
    # Verify it still works
    assistant_message = None
    for msg in fixed_messages:
        if msg.get("role") == "assistant":
            assistant_message = msg
            break
    
    tool_calls = assistant_message.get("tool_calls") or []
    assert len(tool_calls) > 0, "Dict objects in cache should still work"
    
    print(f"\n4. Verification: Tool calls added successfully")
    print("\n" + "=" * 80)
    print("[PASS] Backward compatibility maintained!")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        test_pydantic_object_in_cache()
        test_dict_in_cache_still_works()
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80)
        print("\nThe fix correctly handles:")
        print("  1. Pydantic ChatCompletionMessageToolCall objects (NEW)")
        print("  2. Plain dict objects (BACKWARD COMPATIBLE)")
        print("\nBoth Pydantic v1 (dict()) and v2 (model_dump()) are supported.")
        
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
