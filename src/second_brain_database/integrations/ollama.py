"""Small Ollama HTTP client helper.

This module implements a minimal async client to send prompts to a local Ollama
HTTP server. It tries to be defensive about response shapes because Ollama's
HTTP responses may vary by version. The client uses httpx.AsyncClient which
is already a dependency in the project.

Behavior:
- generate(prompt) -> returns text response from the model (string).
- If the HTTP call fails, raises httpx.HTTPError.

Note: In production you may want to add retries, timeouts, streaming parsing,
and rate limiting. Also consider adding a local cache for repeated prompts.
"""

from __future__ import annotations

from typing import Optional, AsyncGenerator
import json
import httpx
from pydantic import BaseModel

class OllamaClient:
    def __init__(self, base_url: str, model: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def generate(self, prompt: str, model: Optional[str] = None, max_tokens: Optional[int] = None, temperature: float = 0.7, stream: bool = False) -> str:
        """Send a prompt to Ollama and return the output text.

        This uses the /api/generate endpoint if available, otherwise falls back
        to a plain POST and returns text body.
        """
        used_model = model or self.model

        payload = {"prompt": prompt, "stream": stream}
        if used_model:
            payload["model"] = used_model
        if max_tokens:
            payload["options"] = {"num_predict": max_tokens}
        if temperature != 0.7:
            payload.setdefault("options", {})["temperature"] = temperature

        url = "/api/generate"
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()

            if stream:
                # For streaming, return the full response text (caller can parse)
                return resp.text

            # Try JSON parsing first
            try:
                data = resp.json()
            except json.JSONDecodeError:
                return resp.text

            # Ollama newer responses often nest content inside 'content' or choices
            # Try several common shapes.
            if isinstance(data, dict):
                # shape: { 'choices': [ { 'message': { 'content': '...' } } ] }
                choices = data.get("choices")
                if choices and isinstance(choices, list):
                    first = choices[0]
                    # support multiple nesting levels
                    if isinstance(first, dict):
                        # message -> content
                        msg = first.get("message") or first.get("content") or first.get("text")
                        if isinstance(msg, dict) and "content" in msg:
                            return msg["content"]
                        if isinstance(msg, str):
                            return msg

                # direct content
                if "content" in data and isinstance(data["content"], str):
                    return data["content"]

                # direct response (Ollama standard)
                if "response" in data and isinstance(data["response"], str):
                    return data["response"]

                # older shape: { 'text': '...' }
                if "text" in data and isinstance(data["text"], str):
                    return data["text"]

            # Fallback to raw text
            return resp.text

        except httpx.HTTPError:
            # Let caller handle retries/logging
            raise

    async def stream_generate(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """Stream response from Ollama."""
        used_model = model or self.model
        payload = {"prompt": prompt, "stream": True, "model": used_model, "options": {"temperature": temperature}}

        async with self._client.stream("POST", "/api/generate", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                        elif "content" in data:
                            yield data["content"]
                    except json.JSONDecodeError:
                        continue

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["OllamaClient"]
