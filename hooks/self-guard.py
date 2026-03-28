"""
self-guard.py — AI behavior guard hook for Claude Code (PreResponse)

Scans the assistant's pending response for known bad patterns and injects
a warning system message so the model can self-correct before the user sees it.

Detection modes (all configurable via self-guard-config.json):
  E: Sycophancy — immediately agrees when challenged, no analysis
  F: Ask instead of do — says "want me to...?" instead of acting
  G: Acknowledge without action — says "got it" but uses no tools
  Passive wait: defers with "later"/"tomorrow" without concrete tracking

Output: {"systemMessage": "..."} on detection, {} otherwise.
Hook type: PreResponse (exit 0 always)
Dependencies: Python 3.8+ stdlib only
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "self-guard-config.json")


def load_config():
    """Load configuration from self-guard-config.json alongside this script."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_stdin():
    """Read JSON from stdin (Claude Code hook input)."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def load_transcript_tail(transcript_path, n=8):
    """Read the last n messages from the transcript file."""
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


def extract_text(msg):
    """Extract plain text from a message (handles string and content-block formats)."""
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
    """Check if a message contains any tool_use blocks."""
    content = msg.get("content", "")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return True
    return False


def find_last_pair(messages):
    """Find the last assistant message and the user message before it."""
    last_assistant = None
    last_user = None
    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant" and last_assistant is None:
            last_assistant = msg
        elif role == "user" and last_assistant is not None and last_user is None:
            last_user = msg
            break
    return last_assistant, last_user


def matches_any(text, patterns, flags=re.IGNORECASE | re.MULTILINE):
    """Return True if text matches any pattern in the list."""
    for p in patterns:
        try:
            if re.search(p, text, flags):
                return True
        except re.error:
            continue
    return False


def count_matches(text, patterns, flags=re.IGNORECASE | re.MULTILINE):
    """Count how many patterns match the text."""
    count = 0
    for p in patterns:
        try:
            if re.search(p, text, flags):
                count += 1
        except re.error:
            continue
    return count


# ─── Mode F: Ask instead of do ───


def check_mode_f(text, cfg):
    """Detect 'want me to...?' patterns in assistant response."""
    mode_cfg = cfg.get("mode_f", {})
    if not mode_cfg.get("enabled", True):
        return False
    patterns = mode_cfg.get("patterns", []) + mode_cfg.get("patterns_zh", [])
    if not patterns:
        return False
    return matches_any(text, patterns)


# ─── Mode G: Acknowledge without action ───


def check_mode_g(messages, cfg):
    """Detect: user gives change instruction, assistant only acknowledges with text."""
    mode_cfg = cfg.get("mode_g", {})
    if not mode_cfg.get("enabled", True):
        return False

    last_assistant, last_user = find_last_pair(messages)
    if not last_assistant or not last_user:
        return False

    # If assistant used tools, it's not just acknowledging
    if has_tool_use(last_assistant):
        return False

    user_text = extract_text(last_user)
    indicators = mode_cfg.get("change_indicators", []) + mode_cfg.get("change_indicators_zh", [])
    if not indicators:
        return False
    if not matches_any(user_text, indicators):
        return False

    # Check assistant response for acknowledgment words
    assistant_text = extract_text(last_assistant)
    ack_patterns = mode_cfg.get("ack_patterns", []) + mode_cfg.get("ack_patterns_zh", [])
    if not ack_patterns:
        return False
    return matches_any(assistant_text, ack_patterns)


# ─── Mode E: Sycophancy ───


def check_mode_e(messages, cfg):
    """Detect: user challenges, assistant surrenders without analysis."""
    mode_cfg = cfg.get("mode_e", {})
    if not mode_cfg.get("enabled", True):
        return False

    last_assistant, last_user = find_last_pair(messages)
    if not last_assistant or not last_user:
        return False

    user_text = extract_text(last_user)
    challenge_patterns = mode_cfg.get("challenge_patterns", []) + mode_cfg.get("challenge_patterns_zh", [])
    if not challenge_patterns:
        return False
    if not matches_any(user_text, challenge_patterns):
        return False

    assistant_text = extract_text(last_assistant)
    surrender_patterns = mode_cfg.get("surrender_patterns", []) + mode_cfg.get("surrender_patterns_zh", [])
    if not surrender_patterns:
        return False

    surrender_threshold = mode_cfg.get("surrender_threshold", 2)
    max_response_length = mode_cfg.get("max_response_length", 200)

    surrender_count = count_matches(assistant_text, surrender_patterns)

    # Short surrender with no reasoning = sycophancy
    if surrender_count >= surrender_threshold and len(assistant_text) < max_response_length:
        return True

    # Many surrender phrases even in a long response
    if surrender_count >= surrender_threshold + 2:
        return True

    return False


# ─── Passive Wait ───


def check_passive_wait(text, cfg):
    """Detect deferral language ('tomorrow', 'later') without action tracking."""
    pw_cfg = cfg.get("passive_wait", {})
    if not pw_cfg.get("enabled", True):
        return False

    patterns = pw_cfg.get("patterns", []) + pw_cfg.get("patterns_zh", [])
    if not patterns:
        return False
    if not matches_any(text, patterns):
        return False

    # If there's also an action override, it's not passive
    overrides = pw_cfg.get("action_overrides", []) + pw_cfg.get("action_overrides_zh", [])
    if overrides and matches_any(text, overrides):
        return False

    return True


# ─── Main ───


def main():
    config = load_config()
    if config is None:
        # No config file = nothing to check
        print("{}")
        sys.exit(0)

    if not config.get("enabled", True):
        print("{}")
        sys.exit(0)

    input_data = read_stdin()

    transcript_path = input_data.get("transcript_path", "")
    messages = []
    if transcript_path:
        messages = load_transcript_tail(transcript_path, n=8)
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

    # ─── Run all enabled detection modes ───
    warnings = []

    # Mode F: Ask instead of do
    if check_mode_f(assistant_text, config):
        warning = config.get("mode_f", {}).get(
            "warning",
            "Mode F: Your response asks the user for permission instead of acting. "
            "Act directly and report the result."
        )
        warnings.append(warning)

    # Mode G: Acknowledge without action
    if check_mode_g(messages, config):
        warning = config.get("mode_g", {}).get(
            "warning",
            "Mode G: The user gave a change instruction but your response only contains "
            "text acknowledgment with no tool usage. Act first, then describe what you did."
        )
        warnings.append(warning)

    # Mode E: Sycophancy
    if check_mode_e(messages, config):
        warning = config.get("mode_e", {}).get(
            "warning",
            "Mode E: The user challenged your response and you immediately agreed "
            "without analysis. Defend with evidence or explain what was wrong."
        )
        warnings.append(warning)

    # Passive wait
    if check_passive_wait(assistant_text, config):
        warning = config.get("passive_wait", {}).get(
            "warning",
            "Passive waiting: Your response defers action without a concrete reason. "
            "If you can do it now, do it. Otherwise explain why and set up tracking."
        )
        warnings.append(warning)

    if not warnings:
        print("{}")
        sys.exit(0)

    # Build warning message
    severity = "WARNING" if len(warnings) == 1 else "CRITICAL"
    header = f"[SELF-GUARD {severity}] Detected {len(warnings)} behavior pattern(s):\n"
    body = "\n".join(f"\n{i}. {w}" for i, w in enumerate(warnings, 1))

    if len(warnings) >= 2:
        footer = "\n\nMultiple patterns triggered. Correct all of them before responding."
    else:
        footer = "\n\nReview your response and correct the issue."

    result = {"systemMessage": header + body + footer}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
