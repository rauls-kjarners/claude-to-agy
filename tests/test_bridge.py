import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.bridge import format_file_context, delegate, MCPServer


def test_format_file_context_existing_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello Gemini!")

    context = format_file_context([str(test_file)])

    assert f"--- File: {test_file} ---" in context
    assert "Hello Gemini!" in context


def test_format_file_context_missing_file():
    context = format_file_context(["/path/that/does/not/exist.txt"])
    assert "--- File: /path/that/does/not/exist.txt (File not found) ---" in context


def test_format_file_context_empty():
    assert format_file_context([]) == ""


@pytest.mark.asyncio
async def test_delegate_success():
    with patch("src.bridge.run_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = {"success": True, "response": "Success!"}

        result = await delegate("test prompt", [])

        assert result["success"] is True
        assert result["response"] == "Success!"
        mock.assert_called_once()


@pytest.mark.asyncio
async def test_delegate_fallback():
    with patch("src.bridge.run_gemini", new_callable=AsyncMock) as mock:
        mock.side_effect = [
            {"success": False, "error": "Pro failed"},
            {"success": True, "response": "Flash success!"},
        ]

        result = await delegate("test prompt", [])

        assert result["success"] is True
        assert result["response"] == "Flash success!"
        assert mock.call_count == 2


@pytest.mark.asyncio
async def test_delegate_no_fallback():
    with patch("src.bridge.run_gemini", new_callable=AsyncMock) as mock:
        with patch("src.bridge.FALLBACK_MODEL", ""):
            mock.return_value = {"success": False, "error": "Primary failed"}

            result = await delegate("test prompt", [])

            assert result["success"] is False
            assert result["error"] == "Primary failed"
            assert "response" not in result
            assert mock.call_count == 1


@pytest.mark.asyncio
async def test_delegate_with_flash_model():
    with patch("src.bridge.run_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = {"success": True, "response": "Flash result!"}

        result = await delegate("test prompt", [], "gemini-3-flash-preview")

        assert result["success"] is True
        mock.assert_called_once_with("test prompt", [], "gemini-3-flash-preview")


@pytest.mark.asyncio
async def test_delegate_with_invalid_model_defaults_to_primary():
    with patch("src.bridge.run_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = {"success": True, "response": "Pro result!"}

        result = await delegate("test prompt", [], "invalid-model")

        assert result["success"] is True
        mock.assert_called_once_with("test prompt", [], "gemini-3.1-pro-preview")


@pytest.mark.asyncio
async def test_delegate_flash_no_fallback_on_failure():
    """When flash is requested and fails, no further fallback since it's already the fallback model."""
    with patch("src.bridge.run_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = {"success": False, "error": "Flash failed"}

        result = await delegate("test prompt", [], "gemini-3-flash-preview")

        assert result["success"] is False
        assert mock.call_count == 1


@pytest.mark.asyncio
async def test_mcp_initialize():
    mock_writer = MagicMock()
    server = MCPServer(MagicMock(), mock_writer)

    await server._handle_request({"method": "initialize", "id": 1})

    mock_writer.write.assert_called_once()
    mock_writer.flush.assert_called_once()

    response_json = mock_writer.write.call_args[0][0]
    assert '"protocolVersion": "2024-11-05"' in response_json
    assert '"claude-to-gemini"' in response_json


@pytest.mark.asyncio
async def test_mcp_tools_list():
    mock_writer = MagicMock()
    server = MCPServer(MagicMock(), mock_writer)

    await server._handle_request({"method": "tools/list", "id": 1})

    mock_writer.write.assert_called_once()
    response_json = mock_writer.write.call_args[0][0]
    assert '"delegate_to_gemini"' in response_json


@pytest.mark.asyncio
async def test_mcp_tools_list_has_model_param():
    mock_writer = MagicMock()
    server = MCPServer(MagicMock(), mock_writer)

    await server._handle_request({"method": "tools/list", "id": 1})

    response_json = mock_writer.write.call_args[0][0]
    assert '"model"' in response_json
    assert '"flash"' in response_json
    assert '"pro"' in response_json


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
