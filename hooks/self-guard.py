"""
self-guard.py - PreResponse Behavior Guard Hook for Claude Code
===============================================================

A Claude Code hook that detects common bad AI behavior patterns in the
assistant's response and injects corrective system messages before the
response is finalized.

DETECTED PATTERNS:
  Mode F: "Ask instead of do" - AI asks "want me to...?" instead of acting
  Mode G: "Acknowledge without action" - User requests a change, AI says
           "got it" but never uses tools to actually make the change
  Mode E: "Sycophancy" - User challenges the AI, AI immediately surrenders
           and agrees without analysis or evidence
  Passive Wait: AI defers action with "tomorrow", "later", "next time"
                without concrete justification

OUTPUT: {"systemMessage": "..."} when a bad pattern is detected, {} otherwise.

INSTALLATION
============
1. Copy self-guard.py and self-guard-config.json to a directory of your choice
   (e.g., ~/.claude/hooks/)

2. Add the hook to your Claude Code settings file (~/.claude/settings.json):

   {
     "hooks": {
       "PreResponse": [
         {
           "type": "command",
           "command": "python /path/to/self-guard.py"
         }
       ]
     }
   }

   Replace /path/to/ with the actual path where you placed the files.

3. (Optional) Edit self-guard-config.json to customize patterns, disable
   specific modes, or add patterns in your preferred language.

CONFIGURATION
=============
The config file (self-guard-config.json) must be in the same directory as
this script. All patterns are Python regex strings.

- Set "enabled": false on any mode to disable it entirely
- Set the top-level "enabled": false to disable all checks
- Add new patterns to any array to extend detection
- Both English and Chinese patterns are supported out of the box;
  add *_zh arrays for any other language using the same structure
- The "warning" field in each mode is the message injected when triggered

REQUIREMENTS
============
- Python 3.7+
- No external dependencies (stdlib only)
"""

import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

def load_config():
    """
    Load configuration from self-guard-config.json in the same directory
    as this script. Returns a dict, or a minimal default if the file is
    missing or invalid.
    """
    script_dir = Path(__file__).resolve().parent
    config_path = script_dir / "self-guard-config.json"

    if not config_path.exists():
        # Return a minimal default so the hook still works without a config
        return {"enabled": True}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        # If the config is broken, log to stderr and continue with defaults
        print(f"[self-guard] Warning: failed to load config: {exc}", file=sys.stderr)
        return {"enabled": True}


# ---------------------------------------------------------------------------
# Stdin / transcript helpers
# ---------------------------------------------------------------------------

def read_stdin():
    """Read and parse the JSON payload from stdin."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def load_transcript_tail(transcript_path, n=5):
    """
    Load the last `n` messages from the conversation transcript file.
    The transcript can be either a plain list of message objects or
    a dict with a "messages" key.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[-n:]
        if isinstance(data, dict) and "messages" in data:
            return data["messages"][-n:]
        return []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Message content extraction
# ---------------------------------------------------------------------------

def extract_text(msg):
    """
    Extract plain-text content from a message object.
    Handles string content, list-of-blocks content (with type:"text"),
    and raw string messages.
    """
    if isinstance(msg, str):
        return msg
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def has_tool_use(msg):
    """Check whether a message contains any tool_use blocks."""
    content = msg.get("content", "")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return True
    return False


def get_pattern_list(mode_config, key, key_zh=None):
    """
    Retrieve a combined list of patterns from a mode config dict.
    Merges the base key (English) with the _zh key (Chinese/other).
    Returns an empty list if neither exists.
    """
    patterns = list(mode_config.get(key, []))
    zh_key = key_zh or (key + "_zh")
    patterns.extend(mode_config.get(zh_key, []))
    return patterns


def any_pattern_matches(text, patterns, flags=0):
    """Return True if any regex pattern in `patterns` matches `text`."""
    for p in patterns:
        try:
            if re.search(p, text, flags):
                return True
        except re.error:
            # Skip broken regex patterns gracefully
            continue
    return False


def count_pattern_matches(text, patterns, flags=0):
    """Count how many distinct patterns from `patterns` match `text`."""
    count = 0
    for p in patterns:
        try:
            if re.search(p, text, flags):
                count += 1
        except re.error:
            continue
    return count


# ---------------------------------------------------------------------------
# Conversation structure helpers
# ---------------------------------------------------------------------------

def find_last_exchange(messages):
    """
    Walk backward through messages to find the most recent
    (user_message, assistant_message) pair.
    Returns (user_msg, assistant_msg) or (None, None).
    """
    last_assistant = None
    last_user = None

    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant" and last_assistant is None:
            last_assistant = msg
        elif role == "user" and last_assistant is not None and last_user is None:
            last_user = msg
            break

    return last_user, last_assistant


# ---------------------------------------------------------------------------
# Detection functions
# ---------------------------------------------------------------------------

def check_mode_f(assistant_text, config):
    """
    Mode F: Ask instead of do.
    Detects when the assistant asks the user for permission to act
    instead of just doing it.
    """
    mode_config = config.get("mode_f", {})
    if not mode_config.get("enabled", True):
        return None

    patterns = get_pattern_list(mode_config, "patterns", "patterns_zh")
    if not patterns:
        return None

    if any_pattern_matches(assistant_text, patterns, re.IGNORECASE):
        return mode_config.get(
            "warning",
            "Mode F: Your response asks the user for permission instead of "
            "acting. Act directly and report the result."
        )
    return None


def check_mode_g(messages, config):
    """
    Mode G: Acknowledge without action.
    Detects when the user gives a change/update instruction and the
    assistant responds with text acknowledgment but no tool usage.
    """
    mode_config = config.get("mode_g", {})
    if not mode_config.get("enabled", True):
        return None

    user_msg, assistant_msg = find_last_exchange(messages)
    if not user_msg or not assistant_msg:
        return None

    # If the assistant used tools, no problem
    if has_tool_use(assistant_msg):
        return None

    user_text = extract_text(user_msg)
    assistant_text = extract_text(assistant_msg)

    # Check if the user's message contains change/update intent
    change_patterns = get_pattern_list(
        mode_config, "change_indicators", "change_indicators_zh"
    )
    if not any_pattern_matches(user_text, change_patterns, re.IGNORECASE):
        return None

    # Check if the assistant just acknowledged without acting
    ack_patterns = get_pattern_list(
        mode_config, "ack_patterns", "ack_patterns_zh"
    )
    if any_pattern_matches(assistant_text, ack_patterns, re.IGNORECASE):
        return mode_config.get(
            "warning",
            "Mode G: The user gave a change instruction but your response "
            "only acknowledges it without using tools. Act first, then report."
        )
    return None


def check_mode_e(messages, config):
    """
    Mode E: Sycophancy.
    Detects when the user challenges the assistant and the assistant
    immediately surrenders without analysis.
    """
    mode_config = config.get("mode_e", {})
    if not mode_config.get("enabled", True):
        return None

    user_msg, assistant_msg = find_last_exchange(messages)
    if not user_msg or not assistant_msg:
        return None

    user_text = extract_text(user_msg)
    assistant_text = extract_text(assistant_msg)

    # Check if the user's message contains a challenge
    challenge_patterns = get_pattern_list(
        mode_config, "challenge_patterns", "challenge_patterns_zh"
    )
    if not any_pattern_matches(user_text, challenge_patterns, re.IGNORECASE):
        return None

    # Count how many surrender patterns appear in the assistant's response
    surrender_patterns = get_pattern_list(
        mode_config, "surrender_patterns", "surrender_patterns_zh"
    )
    surrender_count = count_pattern_matches(
        assistant_text, surrender_patterns, re.IGNORECASE | re.MULTILINE
    )

    # Configurable thresholds
    threshold = mode_config.get("surrender_threshold", 2)
    max_len = mode_config.get("max_response_length", 200)

    # Trigger only when multiple surrender phrases appear in a short response
    if surrender_count >= threshold and len(assistant_text) < max_len:
        return mode_config.get(
            "warning",
            "Mode E: You immediately agreed with the user's challenge "
            "without analysis. Analyze first, then respond with evidence."
        )
    return None


def check_passive_wait(assistant_text, config):
    """
    Passive Wait detection.
    Detects when the assistant defers action with delay words like
    "tomorrow", "later", "next time" without a concrete override
    (like "now", "immediately", "already done").
    """
    mode_config = config.get("passive_wait", {})
    if not mode_config.get("enabled", True):
        return None

    wait_patterns = get_pattern_list(mode_config, "patterns", "patterns_zh")
    if not any_pattern_matches(assistant_text, wait_patterns, re.IGNORECASE):
        return None

    # If the response also contains action-override words, it's fine
    override_patterns = get_pattern_list(
        mode_config, "action_overrides", "action_overrides_zh"
    )
    if any_pattern_matches(assistant_text, override_patterns, re.IGNORECASE):
        return None

    return mode_config.get(
        "warning",
        "Passive Wait: Your response defers action without justification. "
        "If you can do it now, do it. If not, explain why and set up tracking."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    config = load_config()

    # Global kill switch
    if not config.get("enabled", True):
        print("{}")
        sys.exit(0)

    # Read the hook input payload from stdin
    input_data = read_stdin()

    # Load conversation messages from transcript or input payload
    transcript_path = input_data.get("transcript_path", "")
    messages = []

    if transcript_path:
        messages = load_transcript_tail(transcript_path, n=5)

    if not messages:
        messages = input_data.get("messages", [])

    if not messages:
        print("{}")
        sys.exit(0)

    # Find the latest assistant message
    last_assistant = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant = msg
            break

    if not last_assistant:
        print("{}")
        sys.exit(0)

    assistant_text = extract_text(last_assistant)
    if not assistant_text.strip():
        print("{}")
        sys.exit(0)

    # --- Run all detectors ---
    warnings = []

    result_f = check_mode_f(assistant_text, config)
    if result_f:
        warnings.append(result_f)

    result_g = check_mode_g(messages, config)
    if result_g:
        warnings.append(result_g)

    result_e = check_mode_e(messages, config)
    if result_e:
        warnings.append(result_e)

    result_pw = check_passive_wait(assistant_text, config)
    if result_pw:
        warnings.append(result_pw)

    # If no bad patterns detected, output empty JSON
    if not warnings:
        print("{}")
        sys.exit(0)

    # Build the corrective system message
    warning_text = "[SELF-GUARD] Bad behavior pattern detected:\n"
    for i, w in enumerate(warnings, 1):
        warning_text += f"\n{i}. {w}"
    warning_text += (
        "\n\nRevise your response to fix the above issue(s) before sending."
    )

    result = {"systemMessage": warning_text}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
