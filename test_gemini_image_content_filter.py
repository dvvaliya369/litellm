#!/usr/bin/env python3
"""
Test script to verify that Gemini image generation content filter handling works correctly.
"""
import sys
import os
from unittest.mock import MagicMock

# Add the current directory to the path
sys.path.insert(0, os.path.abspath("."))

import httpx

from litellm.llms.vertex_ai.image_generation.vertex_gemini_transformation import (
    VertexAIGeminiImageGenerationConfig,
)
from litellm.llms.gemini.image_generation.transformation import (
    GoogleImageGenConfig,
)
from litellm.types.utils import ImageResponse


def test_vertex_ai_gemini_image_safety_filter():
    """Test that IMAGE_SAFETY finishReason raises an error in Vertex AI Gemini image generation"""
    config = VertexAIGeminiImageGenerationConfig()

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "finishReason": "IMAGE_SAFETY",
                "content": {
                    "parts": []
                }
            }
        ]
    }
    mock_response.headers = {}

    model_response = ImageResponse()

    try:
        result = config.transform_image_generation_response(
            model="gemini-2.5-flash-image",
            raw_response=mock_response,
            model_response=model_response,
            logging_obj=MagicMock(),
            request_data={},
            optional_params={},
            litellm_params={},
            encoding=None,
        )
        print("ERROR: Expected an exception to be raised for IMAGE_SAFETY finishReason")
        return False
    except Exception as e:
        if "IMAGE_SAFETY" in str(e):
            print(f"✓ Vertex AI Gemini: IMAGE_SAFETY finishReason correctly raises error: {e}")
            return True
        else:
            print(f"ERROR: Wrong exception raised: {e}")
            return False


def test_google_gemini_image_safety_filter():
    """Test that IMAGE_SAFETY finishReason raises an error in Google Gemini image generation"""
    config = GoogleImageGenConfig()

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "finishReason": "IMAGE_SAFETY",
                "content": {
                    "parts": []
                }
            }
        ]
    }
    mock_response.headers = {}

    model_response = ImageResponse()

    try:
        result = config.transform_image_generation_response(
            model="gemini-2.5-flash-image",
            raw_response=mock_response,
            model_response=model_response,
            logging_obj=MagicMock(),
            request_data={},
            optional_params={},
            litellm_params={},
            encoding=None,
        )
        print("ERROR: Expected an exception to be raised for IMAGE_SAFETY finishReason")
        return False
    except Exception as e:
        if "IMAGE_SAFETY" in str(e):
            print(f"✓ Google Gemini: IMAGE_SAFETY finishReason correctly raises error: {e}")
            return True
        else:
            print(f"ERROR: Wrong exception raised: {e}")
            return False


def test_vertex_ai_gemini_safety_filter():
    """Test that SAFETY finishReason raises an error in Vertex AI Gemini image generation"""
    config = VertexAIGeminiImageGenerationConfig()

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "finishReason": "SAFETY",
                "content": {
                    "parts": []
                }
            }
        ]
    }
    mock_response.headers = {}

    model_response = ImageResponse()

    try:
        result = config.transform_image_generation_response(
            model="gemini-2.5-flash-image",
            raw_response=mock_response,
            model_response=model_response,
            logging_obj=MagicMock(),
            request_data={},
            optional_params={},
            litellm_params={},
            encoding=None,
        )
        print("ERROR: Expected an exception to be raised for SAFETY finishReason")
        return False
    except Exception as e:
        if "SAFETY" in str(e):
            print(f"✓ Vertex AI Gemini: SAFETY finishReason correctly raises error: {e}")
            return True
        else:
            print(f"ERROR: Wrong exception raised: {e}")
            return False


def test_vertex_ai_gemini_normal_response():
    """Test that normal responses still work correctly in Vertex AI Gemini"""
    config = VertexAIGeminiImageGenerationConfig()

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": "base64_encoded_image_data",
                            }
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 93,
            "promptTokensDetails": [
                {"modality": "TEXT", "tokenCount": 54},
                {"modality": "IMAGE", "tokenCount": 39}
            ],
            "candidatesTokenCount": 17,
            "totalTokenCount": 110,
        }
    }
    mock_response.headers = {}

    model_response = ImageResponse()

    try:
        result = config.transform_image_generation_response(
            model="gemini-2.5-flash-image",
            raw_response=mock_response,
            model_response=model_response,
            logging_obj=MagicMock(),
            request_data={},
            optional_params={},
            litellm_params={},
            encoding=None,
        )
        if len(result.data) == 1 and result.data[0].b64_json == "base64_encoded_image_data":
            print("✓ Vertex AI Gemini: Normal response with STOP finishReason works correctly")
            return True
        else:
            print(f"ERROR: Unexpected result: {result}")
            return False
    except Exception as e:
        print(f"ERROR: Unexpected exception for normal response: {e}")
        return False


if __name__ == "__main__":
    print("Testing Gemini image generation content filter handling...\n")

    results = []
    results.append(test_vertex_ai_gemini_image_safety_filter())
    results.append(test_google_gemini_image_safety_filter())
    results.append(test_vertex_ai_gemini_safety_filter())
    results.append(test_vertex_ai_gemini_normal_response())

    print(f"\n{'='*60}")
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print(f"{'='*60}")

    if all(results):
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)
