"""End-to-end tests for self-guard.py against Claude Code's real transcript layout.

Claude Code's JSONL transcript nests each message under a "message" key and
writes every content block / tool result as its own line, e.g.:

    {"type": "user", "message": {"role": "user", "content": "..."}}
    {"type": "assistant", "message": {"role": "assistant", "content": [{...}]}}

Run:  python -m unittest discover -s hooks/tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "self-guard.py")


def user(content):
    return {"type": "user", "message": {"role": "user", "content": content}}


def assistant(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def text(t):
    return {"type": "text", "text": t}


def tool_use(name="Edit"):
    return {"type": "tool_use", "id": "toolu_1", "name": name, "input": {}}


def tool_result():
    return user([{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}])


def run_hook(entries, last_message, stop_hook_active=False):
    """Write entries as a JSONL transcript, run the hook, return parsed stdout."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "transcript.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        payload = {
            "stop_hook_active": stop_hook_active,
            "last_assistant_message": last_message,
            "transcript_path": path,
        }
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


NOISE = {"type": "queue-operation", "operation": "enqueue"}


class TranscriptLayoutTests(unittest.TestCase):
    def test_mode_g_fires_on_nested_message_transcript(self):
        entries = [NOISE, user("change the limit to 5 seconds"), assistant(text("Got it, will do."))]
        out = run_hook(entries, "Got it, will do.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("Mode G", out["reason"])

    def test_mode_g_not_fired_when_tools_used_earlier_in_turn(self):
        # Final text block is its own line; the tool_use sits in an earlier line.
        entries = [
            user("change the limit to 5 seconds"),
            assistant(tool_use()),
            tool_result(),
            assistant(text("Done - sure, the timeout is now 5.")),
        ]
        out = run_hook(entries, "Done - sure, the timeout is now 5.")
        self.assertNotEqual(out.get("decision"), "block")

    def test_tool_result_is_not_treated_as_user_instruction(self):
        # Last *human* prompt is a question, not a change request, so Mode G
        # must not trigger just because a tool_result precedes the reply.
        entries = [
            user("what does the timeout default to?"),
            assistant(tool_use("Read")),
            tool_result(),
            assistant(text("Understood - it defaults to 10 seconds.")),
        ]
        out = run_hook(entries, "Understood - it defaults to 10 seconds.")
        self.assertNotEqual(out.get("decision"), "block")

    def test_mode_e_fires_on_nested_message_transcript(self):
        entries = [
            user("that's wrong"),
            assistant(text("You're right, my mistake. I apologize.")),
        ]
        out = run_hook(entries, "You're right, my mistake. I apologize.")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("Mode E", out["reason"])

    def test_flat_role_layout_still_supported(self):
        entries = [
            {"role": "user", "content": "that's wrong"},
            {"role": "assistant", "content": "You're right, my mistake. I apologize."},
        ]
        out = run_hook(entries, "You're right, my mistake. I apologize.")
        self.assertEqual(out.get("decision"), "block")

    def test_clean_reply_passes(self):
        entries = [user("fix the bug"), assistant(tool_use()), tool_result(), assistant(text("Fixed the null check on line 42."))]
        out = run_hook(entries, "Fixed the null check on line 42.")
        self.assertEqual(out, {})

    def test_stop_hook_active_never_blocks(self):
        entries = [user("that's wrong"), assistant(text("You're right, my mistake."))]
        out = run_hook(entries, "Want me to fix that?", stop_hook_active=True)
        self.assertEqual(out, {})


if __name__ == "__main__":
    unittest.main()
