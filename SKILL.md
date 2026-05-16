---
name: claude-to-gemini
description: Offloads heavy, token-intensive reasoning and search tasks to Gemini via MCP. MANDATORY delegation for grep, git diff, git log, large files, multi-file analysis.
---

# Skill: claude-to-gemini

This workspace is equipped with a custom MCP bridge that connects Claude to the local `gemini` CLI. It enables Claude to safely delegate massive reasoning tasks, huge file reads, and web searches without exhausting its own context window.

## Terminal Command Delegation - MANDATORY

**BEFORE** running ANY of these commands in a terminal, you MUST use `delegate_to_gemini` instead:

- `grep` (any usage, including recursive) - output can be massive and needs analysis
- `git diff` (any usage) - diffs can span thousands of lines across many files
- `git log` (any usage) - history can contain thousands of commits with full messages

**NEVER** run these commands directly. No exceptions.

## When to Use `delegate_to_gemini`
You should automatically use this tool whenever you encounter:
1. **Large files:** Analyzing log files, database dumps, or any file >200 lines. When in doubt, delegate.
2. **Massive context:** Trying to process more than 3 files at once.
3. **Heavy search tools:** Needing to perform `git log`, `git diff`, or `grep`.
4. **Web/external knowledge:** Web searches and documentation lookups.
5. **Adversarial review / plan critique:** Always delegate.

## Model Routing

Default to `pro` for quality. Use `flash` only for simple, low-stakes tasks:

| Model | When to use |
|---|---|
| `pro` | **Default.** Use for anything requiring reasoning, analysis, or accuracy. |
| `flash` | Simple lookups, short summaries, or straightforward search result parsing. |

When in doubt, use `pro`. Pass the `model` parameter (`"flash"` or `"pro"`) when calling `delegate_to_gemini`.

## Configuration
The bridge supports environment variables for tuning:
- `GEMINI_PRIMARY_MODEL` - primary model (default: `gemini-3.1-pro-preview`)
- `GEMINI_FALLBACK_MODEL` - fallback model (default: `gemini-3-flash-preview`)
- `GEMINI_CONNECT_TIMEOUT` - subprocess start timeout in seconds (default: `60`)
- `GEMINI_TOTAL_TIMEOUT` - total execution timeout in seconds (default: `600`)

## Setup Instructions (for users)
If the tool is not already active in your Claude Code environment, run the following command to register it:

```bash
claude mcp add -s user claude-to-gemini python ~/.claude-to-gemini/src/bridge.py
```