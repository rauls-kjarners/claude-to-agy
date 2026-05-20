"""Tests for block-direct-commands.py hook."""

import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(
    os.path.dirname(__file__), "../../src/hooks/block-direct-commands.py"
)


def run_hook(command: str) -> int:
    env = {**os.environ, "CLAUDE_TOOL_INPUT": json.dumps({"command": command})}
    result = subprocess.run([sys.executable, HOOK], env=env)
    return result.returncode


class TestBlockedCommands(unittest.TestCase):
    def assertBlocked(self, cmd):
        self.assertEqual(run_hook(cmd), 1, f"Expected BLOCKED: {cmd!r}")

    def assertAllowed(self, cmd):
        self.assertEqual(run_hook(cmd), 0, f"Expected ALLOWED: {cmd!r}")

    # --- should block ---

    def test_grep_space(self):
        self.assertBlocked("grep foo bar.txt")

    def test_grep_flag(self):
        self.assertBlocked("grep -r 'pattern' .")

    def test_grep_tab(self):
        self.assertBlocked("grep\t-i foo")

    def test_git_diff(self):
        self.assertBlocked("git diff HEAD~1")

    def test_git_diff_staged(self):
        self.assertBlocked("git diff --staged")

    def test_git_log(self):
        self.assertBlocked("git log --oneline -10")

    def test_egrep_blocked(self):
        # egrep contains "grep " as substring — intentionally blocked
        self.assertBlocked("egrep foo bar")

    def test_ls(self):
        self.assertAllowed("ls -la")

    def test_find(self):
        self.assertAllowed("find . -name '*.py'")

    def test_git_status(self):
        self.assertAllowed("git status")

    def test_empty_command(self):
        self.assertAllowed("")

    def test_invalid_json(self):
        # hook should not crash on bad input — exit 0 (allow)
        env = {**os.environ, "CLAUDE_TOOL_INPUT": "not-json"}
        result = subprocess.run([sys.executable, HOOK], env=env)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
