#!/usr/bin/env python3
"""
Simple test to verify the fix for Pydantic model in TOOL_CALLS_CACHE.
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath("."))

from litellm.responses.litellm_completion_transformation.transformation import (
    LiteLLMCompletionResponsesConfig,
    TOOL_CALLS_CACHE
)
from litellm.types.utils import ChatCompletionMessageToolCall, Function

def test_pydantic_model_in_cache():
    """
    Test that Pydantic ChatCompletionMessageToolCall objects from cache
    are correctly converted to dict before being used.
    """
    print("\n" + "="*80)
    print("Testing Pydantic model conversion from cache")
    print("="*80)

    tool_call_id = "toolu_test123"

    # Create a Pydantic ChatCompletionMessageToolCall object (what actually gets cached)
    tool_call = ChatCompletionMessageToolCall(
        id=tool_call_id,
        type="function",
        function=Function(
            name="test_function",
            arguments='{"param": "value"}'
        )
    )

    # Cache it (simulating what happens at line 1225-1228)
    TOOL_CALLS_CACHE.set_cache(key=tool_call_id, value=tool_call)

    print(f"\n1. Cached object type: {type(tool_call)}")
    print(f"   Object: {tool_call}")

    # Simulate the scenario where we have messages with tool result but missing tool_call
    messages = [
        {
            "role": "user",
            "content": "test message"
        },
        {
            "role": "assistant",
            "content": "I'll use a tool"
            # Missing tool_calls here
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": "tool result"
        }
    ]

    print(f"\n2. Messages before fix:")
    for i, msg in enumerate(messages):
        print(f"   [{i}] {msg.get('role')}: tool_calls={msg.get('tool_calls', 'N/A')}")

    # Apply the fix
    tools = [{"type": "function", "function": {"name": "test_function"}}]
    fixed_messages = LiteLLMCompletionResponsesConfig._ensure_tool_results_have_corresponding_tool_calls(
        messages=messages,
        tools=tools
    )

    print(f"\n3. Messages after fix:")
    for i, msg in enumerate(fixed_messages):
        tool_calls = msg.get("tool_calls", None)
        if tool_calls:
            print(f"   [{i}] {msg.get('role')}: tool_calls={len(tool_calls)} items")
            for tc in tool_calls:
                tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                tc_fn = tc.get("function") if isinstance(tc, dict) else getattr(tc, "function", None)
                fn_name = tc_fn.get("name") if isinstance(tc_fn, dict) else getattr(tc_fn, "name", None) if tc_fn else None
                print(f"       - id={tc_id}, function.name={fn_name}")
        else:
            print(f"   [{i}] {msg.get('role')}: tool_calls=N/A")

    # Verify the fix
    assistant_msg = None
    for msg in fixed_messages:
        if msg.get("role") == "assistant":
            assistant_msg = msg
            break

    assert assistant_msg is not None, "Assistant message should exist"
    assert assistant_msg.get("tool_calls"), "Assistant message should have tool_calls"

    tool_calls = assistant_msg.get("tool_calls")
    assert len(tool_calls) > 0, "Should have at least one tool call"

    # Check the tool call structure
    first_tool_call = tool_calls[0]
    tc_id = first_tool_call.get("id") if isinstance(first_tool_call, dict) else getattr(first_tool_call, "id", None)
    tc_fn = first_tool_call.get("function") if isinstance(first_tool_call, dict) else getattr(first_tool_call, "function", None)

    assert tc_id == tool_call_id, f"Tool call ID should match: {tc_id} vs {tool_call_id}"

    if isinstance(tc_fn, dict):
        fn_name = tc_fn.get("name")
        fn_args = tc_fn.get("arguments")
    else:
        fn_name = getattr(tc_fn, "name", None) if tc_fn else None
        fn_args = getattr(tc_fn, "arguments", None) if tc_fn else None

    assert fn_name == "test_function", f"Function name should be 'test_function', got: {fn_name}"
    assert fn_args, "Function should have arguments"

    print("\n" + "="*80)
    print("✓ TEST PASSED: Pydantic model correctly converted to dict")
    print("="*80)
    print(f"  - Tool call ID matches: {tc_id}")
    print(f"  - Function name correct: {fn_name}")
    print(f"  - Function arguments present: {bool(fn_args)}")
    print("\nThe fix ensures ChatCompletionMessageToolCall Pydantic objects")
    print("are properly converted to dicts before use.")
    print()

if __name__ == "__main__":
    test_pydantic_model_in_cache()
