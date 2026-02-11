#!/usr/bin/env python3
"""
Test script to check for content filter finish reason mismatches
"""

import sys
sys.path.insert(0, '/vercel/sandbox')

from litellm.llms.vertex_ai.gemini.vertex_and_google_ai_studio_gemini import VertexGeminiConfig

def test_content_filter_mismatch():
    """
    Check if all flagged finish reasons are also present in the finish reason mapping
    and map to 'content_filter'.
    """
    print("=" * 80)
    print("CONTENT FILTER FINISH REASON MISMATCH ANALYSIS")
    print("=" * 80)
    print()
    
    # Get the flagged finish reasons (used to detect content policy violations)
    flagged = VertexGeminiConfig().get_flagged_finish_reasons()
    print("Flagged Finish Reasons (from get_flagged_finish_reasons):")
    print("-" * 80)
    for reason, description in flagged.items():
        print(f"  {reason}: {description}")
    print()
    
    # Get the finish reason mapping (used to map Vertex AI finish reasons to OpenAI format)
    mapping = VertexGeminiConfig.get_finish_reason_mapping()
    print("Finish Reason Mapping (from get_finish_reason_mapping):")
    print("-" * 80)
    for reason, mapped_value in mapping.items():
        print(f"  {reason} -> {mapped_value}")
    print()
    
    # Check for mismatches
    print("MISMATCH ANALYSIS:")
    print("-" * 80)
    
    mismatches = []
    missing_from_mapping = []
    
    for reason in flagged:
        if reason not in mapping:
            missing_from_mapping.append(reason)
            print(f"  ❌ {reason} is in flagged reasons but NOT in finish reason mapping")
        elif mapping[reason] != "content_filter":
            mismatches.append(reason)
            print(f"  ❌ {reason} is flagged but maps to '{mapping[reason]}' instead of 'content_filter'")
        else:
            print(f"  ✓ {reason} is correctly mapped to 'content_filter'")
    
    print()
    
    # Check for reasons in mapping but not in flagged (these might be OK)
    print("ADDITIONAL CONTENT_FILTER MAPPINGS (not in flagged reasons):")
    print("-" * 80)
    for reason, mapped_value in mapping.items():
        if mapped_value == "content_filter" and reason not in flagged:
            print(f"  ℹ️  {reason} -> content_filter (not in flagged reasons)")
    
    print()
    print("=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    
    if missing_from_mapping:
        print(f"❌ ISSUE FOUND: {len(missing_from_mapping)} flagged reason(s) missing from mapping:")
        for reason in missing_from_mapping:
            print(f"   - {reason}")
        print()
        print("IMPACT:")
        print("  When a response has finishReason={}, it will:".format(missing_from_mapping[0]))
        print("  1. Be detected as a content policy violation (line 2193)")
        print("  2. Call _handle_content_policy_violation() which sets finish_reason='content_filter'")
        print("  3. BUT if it reaches _process_candidates() -> _check_finish_reason(),")
        print("     it won't be in the mapping and will default to 'stop'")
        print()
        print("RECOMMENDATION:")
        print("  Add the missing finish reasons to get_finish_reason_mapping():")
        for reason in missing_from_mapping:
            print(f'    "{reason}": "content_filter",')
    
    if mismatches:
        print(f"❌ ISSUE FOUND: {len(mismatches)} flagged reason(s) with incorrect mapping:")
        for reason in mismatches:
            print(f"   - {reason} maps to '{mapping[reason]}' instead of 'content_filter'")
    
    if not missing_from_mapping and not mismatches:
        print("✓ All flagged finish reasons are correctly mapped to 'content_filter'")
    
    print()
    
    return len(missing_from_mapping) == 0 and len(mismatches) == 0

if __name__ == "__main__":
    success = test_content_filter_mismatch()
    sys.exit(0 if success else 1)
