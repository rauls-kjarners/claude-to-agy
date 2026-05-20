# claude-to-agy

A lightweight MCP bridge that lets Claude Code delegate heavy tasks to the Antigravity CLI (agy) - saving context window and **tokens** for what matters.

## What It Does

Registers a `delegate_to_agy` MCP tool that Claude automatically uses when it encounters:
- **Large files** (>200 lines) - logs, dumps, generated code
- **Multi-file analysis** (>3 files at once)
- **Deep searches** - `git log`, `git diff`, `grep`
- **Web lookups** - documentation, external knowledge
- **Adversarial review / plan critique** - always delegated

Claude sends a prompt + file paths → the bridge runs `agy` CLI → returns the result.

## Requirements

- Python 3.12+
- [`agy` CLI](https://antigravity.google/docs/cli-getting-started) installed and authenticated
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Installation

```bash
# 1. Clone anywhere on your machine
git clone https://github.com/rauls-kjarners/claude-to-agy.git ~/.claude-to-agy

# 2. Register the MCP server (global - works in any project)
claude mcp add -s user claude-to-agy python3 ~/.claude-to-agy/src/bridge.py

# 3. Copy the rules file into any project where you want delegation
cp ~/.claude-to-agy/CLAUDE.md /path/to/your/project/CLAUDE.md
```

That's it. Claude will now automatically delegate heavy tasks to Antigravity CLI in any project that has the `CLAUDE.md` file.

> **Tip:** To enable globally without copying `CLAUDE.md` per project, add the rules to `~/.claude/CLAUDE.md` instead.

### Using as a Skill

This project also includes a `SKILL.md` file, which is the standard format for reusable Claude Code skills. If your setup supports skills, you can use it instead of manually copying `CLAUDE.md`:

```bash
claude skill add ~/.claude-to-agy/SKILL.md
```

> **Note:** You still need the MCP server registered (step 2 above). The skill provides the rules, MCP provides the tool.

## Configuration

All settings are optional environment variables:

| Variable | Default | Description |
|---|---|---|
| `AGY_CONNECT_TIMEOUT` | `60` | Seconds to start the agy process |
| `AGY_TOTAL_TIMEOUT` | `600` | Hard timeout for entire execution |


## How It Works

```
User → Claude Code → MCP bridge (bridge.py) → agy CLI → Gemini API
                   ←                        ←         ←
```

1. `CLAUDE.md` instructs Claude when to delegate
2. Claude calls `delegate_to_agy(prompt, cwd, files?)` via MCP
3. `bridge.py` prepends file paths to the prompt
4. Runs `agy --dangerously-skip-permissions --add-dir <cwd> -p "<prompt>"`
5. Returns `{"success": true, "response": "..."}` or `{"success": false, "error": "..."}` back to Claude

## Development

```bash
python -m pytest tests/ -v
```

## License

Apache 2.0
