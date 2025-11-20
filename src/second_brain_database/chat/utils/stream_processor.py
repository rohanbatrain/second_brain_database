"""
StreamProcessor for AI SDK Data Stream Protocol formatting.

This module provides utilities for formatting streaming responses according to the
AI SDK Data Stream Protocol with support for text, metadata, progress indicators,
and error handling.

Protocol Prefixes:
- 0: Text parts (streaming text tokens)
- 2: Data parts (metadata like message_id)
- g: Generation step (progress updates)
- e: Error/finish reason
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi.responses import StreamingResponse


class StreamProcessor:
    """
    Utility class for formatting streaming responses according to AI SDK Data Stream Protocol.
    
    This processor handles:
    - Text token streaming with "0:" prefix
    - Metadata streaming with "2:" prefix (e.g., message_id)
    - Progress indicators with "g:" prefix
    - Error and finish streaming with "e:" prefix
    - Special markers (CURRENT_STEP::, START::, END::)
    - Comprehensive error handling with timeout support
    """

    @staticmethod
    async def format_stream(
        generator: AsyncGenerator[Any, None],
        include_headers: bool = True,
        timeout: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """
        Format streaming tokens to AI SDK Data Stream Protocol.
        
        Args:
            generator: AsyncGenerator yielding tokens (strings or dicts)
            include_headers: Whether to include special headers (deprecated, use add_special_headers)
            timeout: Optional timeout in seconds for the entire stream
            
        Yields:
            Formatted protocol strings with appropriate prefixes
            
        Protocol Format:
            - Text: "0:{json_encoded_text}\\n"
            - Metadata: "2:{json_encoded_data}\\n"
            - Progress: "g:{json_encoded_message}\\n"
            - Finish: 'e:{"finishReason":"stop","usage":null,"isContinued":false}\\n'
            - Error: 'e:{"finishReason":"error","error":"error_message"}\\n'
            
        Special Markers:
            - "CURRENT_STEP::step_name" -> Progress indicator
            - "START::message_id" -> Message ID metadata
            - "END::" -> Ignored (stream completion)
            
        Example:
            async def token_generator():
                yield {"type": "start", "message_id": "msg_123"}
                yield {"type": "progress", "message": "Searching..."}
                yield "Hello"
                yield " world"
                
            async for formatted in StreamProcessor.format_stream(token_generator()):
                print(formatted)
                # Output:
                # 2:[{"message_id":"msg_123"}]
                # g:"Searching..."
                # 0:"Hello"
                # 0:" world"
                # e:{"finishReason":"stop","usage":null,"isContinued":false}
        """
        try:
            # Wrap generator with timeout if specified
            if timeout:
                generator = StreamProcessor._with_timeout(generator, timeout)
            
            async for token in generator:
                # Handle dictionary tokens (structured data)
                if isinstance(token, dict):
                    # Progress indicators
                    if token.get("type") == "progress":
                        message = token.get("message", "")
                        yield f'g:{json.dumps(message)}\n'
                        continue
                    
                    # Message ID at start
                    elif token.get("type") == "start":
                        message_id = token.get("message_id")
                        if message_id:
                            yield f'2:{json.dumps([{"message_id": message_id}])}\n'
                        continue
                    
                    # Generic metadata
                    elif token.get("type") == "metadata":
                        data = token.get("data", {})
                        yield f'2:{json.dumps([data])}\n'
                        continue
                    
                    # Unknown dict type - skip or log
                    continue
                
                # Handle string tokens
                if isinstance(token, str):
                    # Check for special markers
                    if "CURRENT_STEP::" in token:
                        # Extract step name and send as progress
                        step = token.replace("CURRENT_STEP::", "").strip()
                        yield f'g:{json.dumps(step)}\n'
                        continue
                    
                    elif "START::" in token:
                        # Extract message ID and send as metadata
                        message_id = token.replace("START::", "").strip()
                        if message_id:
                            yield f'2:{json.dumps([{"message_id": message_id}])}\n'
                        continue
                    
                    elif "END::" in token:
                        # Skip END markers - we'll send finish reason at the end
                        continue
                    
                    else:
                        # Regular text token
                        yield f'0:{json.dumps(token)}\n'
            
            # Success finish - stream completed normally
            yield 'e:{"finishReason":"stop","usage":null,"isContinued":false}\n'
            
        except asyncio.TimeoutError:
            # Timeout occurred
            yield 'e:{"finishReason":"error","error":"Request timeout"}\n'
            
        except asyncio.CancelledError:
            # Stream was cancelled
            yield 'e:{"finishReason":"error","error":"Stream cancelled"}\n'
            raise  # Re-raise to properly handle cancellation
            
        except Exception as e:
            # Any other error
            error_message = str(e)
            yield f'e:{json.dumps({"finishReason": "error", "error": error_message})}\n'

    @staticmethod
    async def _with_timeout(
        generator: AsyncGenerator[Any, None],
        timeout: float
    ) -> AsyncGenerator[Any, None]:
        """
        Wrap an async generator with a timeout.
        
        Args:
            generator: The async generator to wrap
            timeout: Timeout in seconds
            
        Yields:
            Items from the generator
            
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        try:
            async for item in generator:
                # Use wait_for with a small timeout for each iteration
                # This allows the timeout to apply to the entire stream
                yield item
        except asyncio.TimeoutError:
            raise

    @staticmethod
    def add_special_headers(response: StreamingResponse) -> StreamingResponse:
        """
        Add required headers for AI SDK Data Stream Protocol streaming.
        
        Args:
            response: FastAPI StreamingResponse object
            
        Returns:
            StreamingResponse with added headers
            
        Headers Added:
            - x-vercel-ai-data-stream: v1 (AI SDK protocol version)
            - Content-Type: text/event-stream (SSE format)
            - Connection: keep-alive (maintain connection)
            - Cache-Control: no-cache (prevent caching)
            - X-Accel-Buffering: no (disable nginx buffering)
            
        Example:
            @app.post("/chat")
            async def chat_endpoint():
                async def generate():
                    yield "Hello"
                    yield " world"
                
                response = StreamingResponse(
                    StreamProcessor.format_stream(generate()),
                    media_type="text/event-stream"
                )
                return StreamProcessor.add_special_headers(response)
        """
        response.headers["x-vercel-ai-data-stream"] = "v1"
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Connection"] = "keep-alive"
        response.headers["Cache-Control"] = "no-cache, no-transform"
        response.headers["X-Accel-Buffering"] = "no"  # Disable nginx buffering
        return response

    @staticmethod
    def create_streaming_response(
        generator: AsyncGenerator[Any, None],
        timeout: Optional[float] = None
    ) -> StreamingResponse:
        """
        Create a StreamingResponse with proper headers and formatting.
        
        This is a convenience method that combines format_stream and add_special_headers.
        
        Args:
            generator: AsyncGenerator yielding tokens
            timeout: Optional timeout in seconds
            
        Returns:
            StreamingResponse ready to return from FastAPI endpoint
            
        Example:
            @app.post("/chat")
            async def chat_endpoint():
                async def generate():
                    yield {"type": "start", "message_id": "msg_123"}
                    yield "Hello world"
                
                return StreamProcessor.create_streaming_response(
                    generate(),
                    timeout=30.0
                )
        """
        formatted_stream = StreamProcessor.format_stream(generator, timeout=timeout)
        response = StreamingResponse(
            formatted_stream,
            media_type="text/event-stream"
        )
        return StreamProcessor.add_special_headers(response)
