"""
Simple test to verify the fix for ChatCompletionMessageToolCall caching issue.
"""
import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))
from litellm.responses.litellm_completion_transformation.transformation import (
    LiteLLMCompletionResponsesConfig,
    TOOL_CALLS_CACHE
)
from litellm.types.utils import ChatCompletionMessageToolCall, Function


def test_fix_with_pydantic_model():
    """
    Test that the fix handles ChatCompletionMessageToolCall (Pydantic model) objects.
    """
    shell_tool = {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Runs a shell command, and returns its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "array", "items": {"type": "string"}},
                    "workdir": {"type": "string", "description": "The working directory for the command."}
                },
                "required": ["command"]
            }
        }
    }

    tool_call_id = "toolu_0123456789abcdef"

    # Create a ChatCompletionMessageToolCall object (Pydantic model)
    # This is what gets cached when transform_chat_completion_tools_to_responses_tools is called
    tool_call_obj = ChatCompletionMessageToolCall(
        id=tool_call_id,
        type="function",
        function=Function(
            name="shell",
            arguments='{"command": ["echo", "hello"]}'
        )
    )

    # Cache it (simulating what happens in transform_chat_completion_tools_to_responses_tools)
    TOOL_CALLS_CACHE.set_cache(
        key=tool_call_id,
        value=tool_call_obj  # Note: Pydantic object, not dict
    )

    # Simulate messages that would be reconstructed from spend logs
    messages_missing_tool_calls = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "make a hello world html file"}]
        },
        {
            "role": "assistant",
            "content": "I'll help you create that HTML file."
        },
        {
            "role": "tool",
            "content": '{"output":"<html>...</html>"}',
            "tool_call_id": tool_call_id
        }
    ]

    # Apply the fix
    fixed_messages = LiteLLMCompletionResponsesConfig._ensure_tool_results_have_corresponding_tool_calls(
        messages=messages_missing_tool_calls,
        tools=[shell_tool]
    )

    # Verify the fix worked
    assistant_message = None
    for msg in fixed_messages:
        if msg.get("role") == "assistant":
            assistant_message = msg
            break

    assert assistant_message is not None, "Assistant message should be present"

    # Check if tool_calls were added
    tool_calls = assistant_message.get("tool_calls") or []
    assert len(tool_calls) > 0, (
        f"Fix should have added tool_calls to assistant message. "
        f"Found: {json.dumps(assistant_message, indent=2, default=str)}"
    )

    # Verify the tool_call has the correct ID
    found_tool_call = False
    for tool_call in tool_calls:
        tool_call_id_from_msg = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
        if tool_call_id_from_msg == tool_call_id:
            found_tool_call = True
            # Also verify function details
            func = tool_call.get("function") if isinstance(tool_call, dict) else getattr(tool_call, "function", None)
            if func:
                func_name = func.get("name") if isinstance(func, dict) else getattr(func, "name", None)
                func_args = func.get("arguments") if isinstance(func, dict) else getattr(func, "arguments", None)
                print(f"✓ Tool call reconstructed: {func_name}({func_args})")
            break

    assert found_tool_call, (
        f"Tool call with ID {tool_call_id} should be present in assistant message. "
        f"Found tool_calls: {json.dumps(tool_calls, indent=2, default=str)}"
    )

    print("\n" + "=" * 80)
    print("[PASS] Fix verified: ChatCompletionMessageToolCall (Pydantic) handled correctly")
    print("=" * 80)
    print(f"  Tool calls count: {len(tool_calls)}")
    print(f"  Tool call ID: {tool_call_id}")
    print("\nThe fix successfully converts Pydantic ChatCompletionMessageToolCall objects")
    print("to dicts before using them in _create_tool_call_chunk().")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_fix_with_pydantic_model()
        print("\n✓ All tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
