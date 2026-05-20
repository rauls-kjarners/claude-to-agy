"""PreToolUse hook: blocks grep, git diff, git log from running directly.

Claude Code hooks run for ALL agents (main + subagents), so this enforces
delegation even when subagents ignore CLAUDE.md instructions.

Usage in ~/.claude/settings.json or .claude/settings.json:

  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/claude-to-agy/hooks/block-direct-commands.py",
            "onError": "block"
          }
        ]
      }
    ]
  }
"""

import sys
import json
import os

BANNED_PATTERNS = [
    "grep ",
    "grep\t",
    "grep -",
    "git diff",
    "git log",
]

raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
try:
    cmd = json.loads(raw).get("command", "")
except Exception:
    cmd = ""

if any(pattern in cmd for pattern in BANNED_PATTERNS):
    print(
        "BLOCKED: grep/git diff/git log cannot be run directly. "
        "If you are a subagent, return control to the parent agent "
        "and instruct it to retry this task using delegate_to_agy."
    )
    sys.exit(1)

