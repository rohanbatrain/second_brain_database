"""Unit tests for StreamProcessor."""

import asyncio
import json
import pytest

from second_brain_database.chat.utils.stream_processor import StreamProcessor


class TestStreamProcessor:
    """Test StreamProcessor functionality."""

    @pytest.mark.asyncio
    async def test_format_stream_text_tokens(self):
        """Test text streaming with '0:' prefix."""
        async def mock_generator():
            yield "Hello"
            yield " "
            yield "world"
            yield "!"
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # Check text tokens have '0:' prefix
        assert '0:"Hello"\n' in result
        assert '0:" "\n' in result
        assert '0:"world"\n' in result
        assert '0:"!"\n' in result
        
        # Check finish message
        assert any('e:' in chunk and 'finishReason":"stop' in chunk for chunk in result)

    @pytest.mark.asyncio
    async def test_format_stream_metadata(self):
        """Test metadata streaming with '2:' prefix."""
        async def mock_generator():
            yield {"type": "start", "message_id": "msg_123"}
            yield "Hello"
            yield {"type": "metadata", "data": {"tokens": 10}}
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # Check metadata has '2:' prefix
        metadata_chunks = [c for c in result if c.startswith('2:')]
        assert len(metadata_chunks) >= 1
        
        # Verify message_id in metadata
        assert any('message_id' in chunk for chunk in metadata_chunks)

    @pytest.mark.asyncio
    async def test_format_stream_progress_indicators(self):
        """Test progress indicators with 'g:' prefix."""
        async def mock_generator():
            yield {"type": "progress", "message": "Searching database..."}
            yield "Result"
            yield {"type": "progress", "message": "Found 5 items"}
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # Check progress indicators have 'g:' prefix
        progress_chunks = [c for c in result if c.startswith('g:')]
        assert len(progress_chunks) == 2
        assert any('Searching database' in chunk for chunk in progress_chunks)
        assert any('Found 5 items' in chunk for chunk in progress_chunks)

    @pytest.mark.asyncio
    async def test_format_stream_special_markers(self):
        """Test special marker handling (CURRENT_STEP::, START::, END::)."""
        async def mock_generator():
            yield "START::msg_123"
            yield "CURRENT_STEP::Processing query"
            yield "Some text"
            yield "END::complete"
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # START:: should be converted to metadata
        assert any('2:' in chunk and 'message_id' in chunk for chunk in result)
        
        # CURRENT_STEP:: should be converted to progress
        assert any('g:' in chunk and 'Processing query' in chunk for chunk in result)
        
        # END:: should be skipped
        assert not any('END::' in chunk for chunk in result)
        
        # Regular text should be present
        assert any('0:"Some text"' in chunk for chunk in result)

    @pytest.mark.asyncio
    async def test_format_stream_error_handling(self):
        """Test error streaming with 'e:' prefix."""
        async def mock_generator():
            yield "Hello"
            raise ValueError("Test error")
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # Check error message has 'e:' prefix
        error_chunks = [c for c in result if c.startswith('e:')]
        assert len(error_chunks) == 1
        assert 'finishReason' in error_chunks[0]
        assert 'error' in error_chunks[0]

    @pytest.mark.asyncio
    async def test_format_stream_timeout(self):
        """Test timeout handling."""
        async def mock_generator():
            yield "Hello"
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError()
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # Check timeout error message
        error_chunks = [c for c in result if c.startswith('e:')]
        assert len(error_chunks) == 1
        assert 'timeout' in error_chunks[0].lower()

    @pytest.mark.asyncio
    async def test_format_stream_empty_generator(self):
        """Test handling empty generator."""
        async def mock_generator():
            return
            yield  # Never reached
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # Should still have finish message
        assert any('e:' in chunk and 'finishReason":"stop' in chunk for chunk in result)

    @pytest.mark.asyncio
    async def test_format_stream_mixed_content(self):
        """Test streaming with mixed content types."""
        async def mock_generator():
            yield {"type": "start", "message_id": "msg_123"}
            yield {"type": "progress", "message": "Starting..."}
            yield "Hello"
            yield " "
            yield "world"
            yield {"type": "metadata", "data": {"tokens": 5}}
            yield {"type": "progress", "message": "Complete"}
        
        result = []
        async for chunk in StreamProcessor.format_stream(mock_generator()):
            result.append(chunk)
        
        # Verify all types are present
        assert any(c.startswith('2:') for c in result)  # Metadata
        assert any(c.startswith('g:') for c in result)  # Progress
        assert any(c.startswith('0:') for c in result)  # Text
        assert any(c.startswith('e:') for c in result)  # Finish

    def test_add_special_headers(self):
        """Test adding special headers to streaming response."""
        from fastapi.responses import StreamingResponse
        
        async def mock_generator():
            yield "test"
        
        response = StreamingResponse(mock_generator())
        response = StreamProcessor.add_special_headers(response)
        
        # Check required headers
        assert response.headers["x-vercel-ai-data-stream"] == "v1"
        assert response.headers["Content-Type"] == "text/event-stream"
        assert response.headers["Connection"] == "keep-alive"
        assert "no-cache" in response.headers["Cache-Control"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
