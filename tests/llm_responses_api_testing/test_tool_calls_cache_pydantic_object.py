"""
Test to verify fix for TOOL_CALLS_CACHE storing ChatCompletionMessageToolCall
Pydantic objects instead of plain dicts.

The bug: TOOL_CALLS_CACHE stores ChatCompletionMessageToolCall objects (Pydantic models),
but _ensure_tool_results_have_corresponding_tool_calls expects plain dict objects.
The isinstance(_tool_use_definition, dict) check fails for the Pydantic object,
causing it to be replaced with an empty dict {}, which results in a malformed tool call
with an empty function name and empty arguments.
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath("../.."))

from litellm.responses.litellm_completion_transformation.transformation import (
    LiteLLMCompletionResponsesConfig,
    TOOL_CALLS_CACHE,
)
from litellm.types.utils import ChatCompletionMessageToolCall, Function


class TestToolCallsCachePydanticObject:
    """Tests that TOOL_CALLS_CACHE works correctly with ChatCompletionMessageToolCall objects."""

    def setup_method(self):
        """Clear the cache before each test."""
        TOOL_CALLS_CACHE.cache_dict.clear()

    def test_tool_use_to_dict_with_pydantic_object(self):
        """
        Test that _tool_use_to_dict correctly converts a ChatCompletionMessageToolCall
        to a plain dict.
        """
        tool_call = ChatCompletionMessageToolCall(
            function=Function(
                name="shell",
                arguments='{"command": ["echo", "hello"]}',
            ),
            id="toolu_abc123",
            type="function",
        )

        result = LiteLLMCompletionResponsesConfig._tool_use_to_dict(tool_call)

        assert isinstance(result, dict), "Result should be a plain dict"
        assert result["id"] == "toolu_abc123"
        assert result["type"] == "function"
        assert isinstance(result["function"], dict), "function should be a plain dict"
        assert result["function"]["name"] == "shell"
        assert result["function"]["arguments"] == '{"command": ["echo", "hello"]}'

    def test_tool_use_to_dict_with_plain_dict(self):
        """
        Test that _tool_use_to_dict passes through plain dicts unchanged.
        """
        tool_def = {
            "id": "toolu_abc123",
            "type": "function",
            "function": {
                "name": "shell",
                "arguments": '{"command": ["echo", "hello"]}',
            },
        }

        result = LiteLLMCompletionResponsesConfig._tool_use_to_dict(tool_def)

        assert result is tool_def, "Plain dicts should be returned as-is"

    def test_ensure_tool_results_with_cached_pydantic_object(self):
        """
        Test that _ensure_tool_results_have_corresponding_tool_calls works correctly
        when TOOL_CALLS_CACHE contains a ChatCompletionMessageToolCall object
        (the real-world scenario that triggers the bug).
        """
        tool_call_id = "toolu_pydantic_test_001"

        # Cache a real ChatCompletionMessageToolCall object (not a plain dict)
        # This is what transform_chat_completion_tools_to_responses_tools does
        tool_call_obj = ChatCompletionMessageToolCall(
            function=Function(
                name="shell",
                arguments='{"command": ["echo", "hello"]}',
            ),
            id=tool_call_id,
            type="function",
        )
        TOOL_CALLS_CACHE.set_cache(key=tool_call_id, value=tool_call_obj)

        # Messages with tool_result but missing tool_calls in assistant message
        messages = [
            {
                "role": "assistant",
                "content": "I'll call the tool.",
                # Missing tool_calls - this is the scenario that triggers the bug
            },
            {
                "role": "tool",
                "content": '{"output":"hello"}',
                "tool_call_id": tool_call_id,
            },
        ]

        fixed_messages = LiteLLMCompletionResponsesConfig._ensure_tool_results_have_corresponding_tool_calls(
            messages=messages,
            tools=None,
        )

        # The assistant message should now have tool_calls
        assistant_message = next(
            (msg for msg in fixed_messages if msg.get("role") == "assistant"), None
        )
        assert assistant_message is not None, "Assistant message should be present"

        tool_calls = assistant_message.get("tool_calls", [])
        assert len(tool_calls) > 0, (
            "Assistant message should have tool_calls added from cached Pydantic object"
        )

        # Verify the tool_call has the correct ID and function name
        first_tool_call = tool_calls[0]
        tc_id = (
            first_tool_call.get("id")
            if isinstance(first_tool_call, dict)
            else getattr(first_tool_call, "id", None)
        )
        assert tc_id == tool_call_id, (
            f"Tool call ID should match. Expected: {tool_call_id}, Got: {tc_id}"
        )

        # Critical: verify function name is NOT empty (this was the bug)
        tc_function = (
            first_tool_call.get("function")
            if isinstance(first_tool_call, dict)
            else getattr(first_tool_call, "function", None)
        )
        func_name = (
            tc_function.get("name")
            if isinstance(tc_function, dict)
            else getattr(tc_function, "name", None)
        )
        assert func_name == "shell", (
            f"Function name should be 'shell', not empty. Got: '{func_name}'. "
            "This indicates the Pydantic object was incorrectly replaced with an empty dict."
        )

        func_args = (
            tc_function.get("arguments")
            if isinstance(tc_function, dict)
            else getattr(tc_function, "arguments", None)
        )
        assert func_args is not None and func_args != "{}", (
            f"Function arguments should contain the original arguments, not empty. Got: '{func_args}'"
        )

    def test_create_tool_call_chunk_with_function_object(self):
        """
        Test that _create_tool_call_chunk handles a dict whose 'function' value
        is a Function object (not a plain dict) — a secondary defense.
        """
        # Simulate a dict-like definition where function is a Function object
        func = Function(
            name="get_weather",
            arguments='{"latitude":48.8566,"longitude":2.3522}',
        )
        tool_def = {
            "id": "toolu_func_test",
            "type": "function",
            "function": func,  # Function object, not a dict
        }

        chunk = LiteLLMCompletionResponsesConfig._create_tool_call_chunk(
            tool_def, "toolu_func_test", 0
        )

        # ChatCompletionToolCallChunk is a TypedDict, so access via dict keys
        assert chunk["id"] == "toolu_func_test"
        assert chunk["function"]["name"] == "get_weather"
        assert "48.8566" in chunk["function"]["arguments"]

    def test_end_to_end_cached_pydantic_object_produces_valid_tool_call(self):
        """
        End-to-end test: cache a ChatCompletionMessageToolCall, then verify
        the full pipeline produces a valid tool call chunk with correct data.
        """
        tool_call_id = "toolu_e2e_test_001"

        tool_call_obj = ChatCompletionMessageToolCall(
            function=Function(
                name="read_file",
                arguments='{"path": "/tmp/test.txt"}',
            ),
            id=tool_call_id,
            type="function",
        )
        TOOL_CALLS_CACHE.set_cache(key=tool_call_id, value=tool_call_obj)

        shell_tool = {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Reads a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }

        messages = [
            {"role": "user", "content": "Read the file"},
            {
                "role": "assistant",
                "content": "I'll read that file for you.",
            },
            {
                "role": "tool",
                "content": '{"content":"file contents here"}',
                "tool_call_id": tool_call_id,
            },
        ]

        fixed_messages = LiteLLMCompletionResponsesConfig._ensure_tool_results_have_corresponding_tool_calls(
            messages=messages,
            tools=[shell_tool],
        )

        assistant_msg = next(
            (msg for msg in fixed_messages if msg.get("role") == "assistant"), None
        )
        assert assistant_msg is not None

        tool_calls = assistant_msg.get("tool_calls", [])
        assert len(tool_calls) == 1, f"Expected 1 tool call, got {len(tool_calls)}"

        tc = tool_calls[0]
        tc_func = tc.function if hasattr(tc, "function") else tc.get("function")
        tc_name = tc_func.name if hasattr(tc_func, "name") else tc_func.get("name")
        tc_args = (
            tc_func.arguments
            if hasattr(tc_func, "arguments")
            else tc_func.get("arguments")
        )

        assert tc_name == "read_file", (
            f"Expected function name 'read_file', got '{tc_name}'"
        )
        assert "/tmp/test.txt" in tc_args, (
            f"Expected arguments to contain path, got '{tc_args}'"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
