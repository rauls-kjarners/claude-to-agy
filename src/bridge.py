"""Claude-to-Gemini MCP Bridge.

A zero-dependency MCP server that delegates tasks to the Gemini CLI
with automatic model fallback and configurable timeouts.
"""

import sys
import json
import asyncio
import os
import logging
from typing import IO, TypedDict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration via environment variables
CONNECT_TIMEOUT = int(os.environ.get("GEMINI_CONNECT_TIMEOUT", "60"))
TOTAL_TIMEOUT = int(os.environ.get("GEMINI_TOTAL_TIMEOUT", "600"))
PRIMARY_MODEL = os.environ.get("GEMINI_PRIMARY_MODEL", "gemini-3.1-pro-preview")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview")


class GeminiResult(TypedDict, total=False):
    success: bool
    response: str
    error: str


def format_file_context(files: list[str]) -> str:
    """Read files and format them into a context string."""
    if not files:
        return ""

    parts: list[str] = []
    for file_path in files:
        if not os.path.exists(file_path):
            parts.append(f"--- File: {file_path} (File not found) ---\n")
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            parts.append(f"--- File: {file_path} ---\n{content}\n")
        except Exception as e:
            parts.append(f"--- File: {file_path} (Error reading: {e}) ---\n")

    return "\n".join(parts) + "\n"


async def run_gemini(prompt: str, files: list[str], model: str) -> GeminiResult:
    """Run the gemini CLI subprocess with timeout protection."""
    file_context = format_file_context(files)
    full_prompt = file_context + prompt
    cmd = ["gemini", "-p", full_prompt, "-m", model]

    try:
        process = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=CONNECT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return GeminiResult(success=False, error=f"Connect timeout ({CONNECT_TIMEOUT}s) exceeded.")
    except Exception as e:
        return GeminiResult(success=False, error=f"Failed to start gemini: {e}")

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=TOTAL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return GeminiResult(success=False, error=f"Total timeout ({TOTAL_TIMEOUT}s) exceeded.")

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if process.returncode != 0:
        return GeminiResult(
            success=False,
            error=f"Process exited with code {process.returncode}. Stderr: {stderr}",
        )

    return GeminiResult(success=True, response=stdout)


async def handle_call(prompt: str, files: list[str], model: str = "") -> GeminiResult:
    """Try requested model (or primary default), fall back on failure."""
    target_model = model if model in (PRIMARY_MODEL, FALLBACK_MODEL) else PRIMARY_MODEL
    result = await run_gemini(prompt, files, target_model)

    if not result["success"] and FALLBACK_MODEL and target_model != FALLBACK_MODEL:
        logger.warning("Model (%s) failed: %s. Retrying with fallback (%s).", target_model, result["error"], FALLBACK_MODEL)
        result = await run_gemini(prompt, files, FALLBACK_MODEL)
    elif not result["success"] and (not FALLBACK_MODEL or target_model == FALLBACK_MODEL):
        logger.error("Model (%s) failed and no further fallback available.", target_model)

    return result


class MCPServer:
    """Minimal MCP JSON-RPC server over stdio."""

    def __init__(self, reader: asyncio.StreamReader, writer: IO[str]):
        self.reader = reader
        self.writer = writer

    def _send(self, response: dict) -> None:
        self.writer.write(json.dumps(response) + "\n")
        self.writer.flush()

    def _result(self, req_id: int | str | None, result: dict) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _error(self, req_id: int | str | None, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

    async def run(self) -> None:
        while True:
            try:
                line = await self.reader.readline()
                if not line:
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                req = json.loads(line_str)
                await self._handle_request(req)

            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON received: %s", e)
            except Exception as e:
                logger.error("Error handling request: %s", e)

    async def _handle_request(self, req: dict) -> None:
        method = req.get("method")
        req_id = req.get("id")

        if method == "ping":
            self._result(req_id, {})

        elif method == "initialize":
            self._result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "claude-to-gemini", "version": "1.1.0"},
            })

        elif method == "notifications/initialized":
            pass  # No response needed for notifications

        elif method == "tools/list":
            self._result(req_id, {
                "tools": [{
                    "name": "delegate_to_gemini",
                    "description": "Delegate complex reasoning, large file analysis, or deep search to Gemini.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "The detailed prompt/instructions for Gemini."},
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of absolute file paths to include as context.",
                            },
                            "model": {
                                "type": "string",
                                "enum": ["flash", "pro"],
                                "description": "Optional. 'flash' for fast simple tasks, 'pro' for complex reasoning. Defaults to pro.",
                            },
                        },
                        "required": ["prompt"],
                    },
                }],
            })

        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})

            if name == "delegate_to_gemini":
                model_arg = args.get("model", "")
                model_map = {"flash": FALLBACK_MODEL, "pro": PRIMARY_MODEL}
                result = await handle_call(args.get("prompt", ""), args.get("files", []), model_map.get(model_arg, ""))
                self._result(req_id, {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                })
            else:
                self._error(req_id, -32601, f"Unknown tool: {name}")

        else:
            if req_id is not None:  # Don't error on notifications
                self._error(req_id, -32601, f"Unknown method: {method}")


async def main() -> None:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    server = MCPServer(reader, sys.stdout)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())