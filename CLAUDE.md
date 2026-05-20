# Claude-to-Antigravity Delegation Rules

You are equipped with a custom MCP tool called `delegate_to_agy`. You **MUST** use this tool to offload heavy, token-intensive tasks to save your own context window.

## Terminal Command Delegation - MANDATORY

**BEFORE** running ANY of these commands in a terminal, you MUST use `delegate_to_agy` instead:

- `grep` (any usage, including recursive) - output can be massive and needs analysis
- `git diff` (any usage) - diffs can span thousands of lines across many files
- `git log` (any usage) - history can contain thousands of commits with full messages

**NEVER** run these commands directly. No exceptions. This applies during ALL phases: planning, exploration, implementation, review.

## Delegation Thresholds - MANDATORY

Use `delegate_to_agy` when ANY of these conditions are met:

1. **File length >200 lines**: Any analysis, review, or reading of files exceeding 200 lines.
2. **Multi-file analysis (>3 files)**: Bug hunting, architecture review, or debugging spanning more than 3 files.
3. **Web/external knowledge**: Any query needing current information or documentation lookups.
4. **Adversarial review / plan critique**: Always delegate.

If you are unsure whether a file is large, delegate it anyway - Antigravity CLI handles the cost, not you.

## STOP & VERIFY

**You are violating these rules if**:
- You answer directly when a trigger condition matches. You MUST delegate.
- You run `grep`, `git diff`, or `git log` in the terminal instead of delegating.
- You read a large file into your context window instead of delegating.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "I already know this code." | Code changes. Delegate to verify. |
| "The file is probably small." | If unsure, delegate. Don't guess. |
| "I can answer this directly." | If a trigger matches, you MUST delegate. No exceptions. |
| "It's faster if I just read it." | Context window conservation is the priority, not speed. |
| "I only need a small part of the file." | Delegate the whole file. Let Antigravity CLI extract what's needed. |


## How to Delegate

- Formulate a clear, detailed `prompt` explaining exactly what needs to be found, analyzed, or searched.
- **Always pass `cwd`** with your current working directory (absolute path) so agy knows where the project is.
- Call `delegate_to_agy` with your `prompt`, `cwd`, and any relevant file paths in the `files` array.
- Await the JSON response and use the summary/data provided by Antigravity CLI to fulfill the user's request.
