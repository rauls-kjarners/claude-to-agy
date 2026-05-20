import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.bridge import run_agy, MCPServer


@pytest.mark.asyncio
async def test_run_agy_success():
    with patch("src.bridge.spawn_agy", new_callable=AsyncMock) as mock_spawn:
        with patch("src.bridge.collect_output", new_callable=AsyncMock) as mock_collect:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_spawn.return_value = mock_process
            mock_collect.return_value = ("Success!", "")

            result = await run_agy("test prompt", "/some/workspace")

            assert result["success"] is True
            assert result["response"] == "Success!"
            mock_spawn.assert_called_once_with("test prompt", "/some/workspace")


@pytest.mark.asyncio
async def test_mcp_initialize():
    mock_writer = MagicMock()
    server = MCPServer(MagicMock(), mock_writer)

    await server._handle_request({"method": "initialize", "id": 1})

    mock_writer.write.assert_called_once()
    mock_writer.flush.assert_called_once()

    response_json = mock_writer.write.call_args[0][0]
    assert '"protocolVersion": "2024-11-05"' in response_json
    assert '"claude-to-agy"' in response_json


@pytest.mark.asyncio
async def test_mcp_tools_list():
    mock_writer = MagicMock()
    server = MCPServer(MagicMock(), mock_writer)

    await server._handle_request({"method": "tools/list", "id": 1})

    mock_writer.write.assert_called_once()
    response_json = mock_writer.write.call_args[0][0]
    assert '"delegate_to_agy"' in response_json


@pytest.mark.asyncio
async def test_mcp_unknown_tool():
    mock_writer = MagicMock()
    server = MCPServer(MagicMock(), mock_writer)

    await server._handle_request(
        {"method": "tools/call", "id": 1, "params": {"name": "nonexistent"}}
    )

    response_json = mock_writer.write.call_args[0][0]
    assert '"error"' in response_json
    assert "Unknown tool" in response_json


@pytest.mark.asyncio
async def test_mcp_unknown_method():
    mock_writer = MagicMock()
    server = MCPServer(MagicMock(), mock_writer)

    await server._handle_request({"method": "unknown/method", "id": 1})

    response_json = mock_writer.write.call_args[0][0]
    assert '"error"' in response_json
