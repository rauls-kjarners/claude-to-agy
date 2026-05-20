import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.bridge import format_file_context, delegate, MCPServer


def test_format_file_context_existing_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello Antigravity!")

    context = format_file_context([str(test_file)])

    assert f"--- File: {test_file} ---" in context
    assert "Hello Antigravity!" in context


def test_format_file_context_missing_file():
    context = format_file_context(["/path/that/does/not/exist.txt"])
    assert "--- File: /path/that/does/not/exist.txt (File not found) ---" in context


def test_format_file_context_empty():
    assert format_file_context([]) == ""


@pytest.mark.asyncio
async def test_delegate_success():
    with patch("src.bridge.run_agy", new_callable=AsyncMock) as mock:
        mock.return_value = {"success": True, "response": "Success!"}

        result = await delegate("test prompt", [])

        assert result["success"] is True
        assert result["response"] == "Success!"
        mock.assert_called_once_with("test prompt", [])


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
