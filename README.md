# claude-to-gemini

A lightweight MCP bridge that lets Claude Code delegate heavy tasks to the Gemini CLI - saving context window and **tokens** for what matters.

## What It Does

Registers a `delegate_to_gemini` MCP tool that Claude automatically uses when it encounters:
- **Large files** (>200 lines) - logs, dumps, generated code
- **Multi-file analysis** (>3 files at once)
- **Deep searches** - `git log`, `git diff`, `grep`
- **Web lookups** - documentation, external knowledge
- **Adversarial review / plan critique** - always delegated

Claude sends a prompt + file paths → the bridge runs `gemini` CLI → returns the result. If the primary model fails, it automatically retries with a fallback model. Claude can also choose between `pro` (default, for complex tasks) and `flash` (for simple lookups).

## Requirements

- Python 3.12+
- [`gemini` CLI](https://github.com/google-gemini/gemini-cli) installed and authenticated
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Installation

```bash
# 1. Clone anywhere on your machine
git clone https://github.com/rauls-kjarners/claude-to-gemini.git ~/.claude-to-gemini

# 2. Register the MCP server (global - works in any project)
claude mcp add -s user claude-to-gemini python3 ~/.claude-to-gemini/src/bridge.py

# 3. Copy the rules file into any project where you want delegation
cp ~/.claude-to-gemini/CLAUDE.md /path/to/your/project/CLAUDE.md
```

That's it. Claude will now automatically delegate heavy tasks to Gemini in any project that has the `CLAUDE.md` file.

> **Tip:** To enable globally without copying `CLAUDE.md` per project, add the rules to `~/.claude/CLAUDE.md` instead.

### Using as a Skill

This project also includes a `SKILL.md` file, which is the standard format for reusable Claude Code skills. If your setup supports skills, you can use it instead of manually copying `CLAUDE.md`:

```bash
claude skill add ~/.claude-to-gemini/SKILL.md
```

> **Note:** You still need the MCP server registered (step 2 above). The skill provides the rules, MCP provides the tool.

## Configuration

All settings are optional environment variables:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_PRIMARY_MODEL` | `gemini-3.1-pro-preview` | Primary model to try first (set to `""` to use gemini's default) |
| `GEMINI_FALLBACK_MODEL` | `gemini-3-flash-preview` | Fallback model if primary fails (set to `""` to use gemini's default) |
| `GEMINI_CONNECT_TIMEOUT` | `60` | Seconds to start the gemini process |
| `GEMINI_TOTAL_TIMEOUT` | `600` | Hard timeout for entire execution |

**Examples:**

```bash
# Use specific models with fallback (default behavior)
export GEMINI_PRIMARY_MODEL="gemini-3.1-pro-preview"
export GEMINI_FALLBACK_MODEL="gemini-3-flash-preview"

# Let gemini CLI choose its own default model (no -m flag)
export GEMINI_PRIMARY_MODEL=""
export GEMINI_FALLBACK_MODEL=""

# Use custom primary, gemini default as fallback
export GEMINI_PRIMARY_MODEL="gemini-2.5-pro"
export GEMINI_FALLBACK_MODEL=""
```

## How It Works

```
User → Claude Code → MCP bridge (bridge.py) → gemini CLI → Gemini API
                   ←                        ←            ←
```

1. `CLAUDE.md` instructs Claude when to delegate
2. Claude calls `delegate_to_gemini(prompt, files, model)` via MCP
3. `bridge.py` reads the files, prepends them to the prompt
4. Runs `gemini -p "<prompt>"` (optionally with `-m <model>` if configured)
5. Returns `{"success": true, "response": "..."}` or `{"success": false, "error": "..."}` back to Claude
6. On failure, automatically retries with fallback model (if configured)

## Development

```bash
python -m pytest tests/ -v
```

## License

Apache 2.0
