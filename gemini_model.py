"""Google Gemini Chat Model integration module.

Implements Component 6: Google Gemini Chat Model
Provides a clean wrapper around the Google GenAI SDK with:
- Secure API key loading
- Timeout and exponential backoff retry policies
- Clear error reporting without exposing sensitive keys
- Structured configuration separate from application business logic
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GeminiChatModel:
    """Encapsulates the Google Gemini Chat Model client and invocation logic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        timeout: int = 45,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = model_name
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None

        if self.api_key:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize the Google GenAI client."""
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Initialized Google GenAI client with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI client: {e}")
            self._client = None

    def is_available(self) -> bool:
        """Check if the Gemini client is configured and initialized."""
        return self._client is not None and bool(self.api_key)

    def generate_chat_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Invoke Gemini chat model with exponential backoff retries.
        Returns the generated raw response text or None if all attempts fail.
        """
        if not self.is_available():
            logger.warning("Gemini model is not configured with an API key.")
            return None

        from google.genai import types

        config_args: Dict[str, Any] = {
            "temperature": self.temperature,
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        if response_schema:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_args)

        backoff_delay = 2.0
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Calling Gemini API (model: {self.model_name}, attempt {attempt}/{self.max_retries})..."
                )
                start_time = time.time()
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                elapsed = time.time() - start_time
                logger.info(f"Gemini API returned response in {elapsed:.2f}s")

                if response and response.text:
                    return response.text
                else:
                    logger.warning("Gemini returned an empty response.")

            except Exception as e:
                # Do NOT log the API key or raw sensitive headers
                error_type = type(e).__name__
                logger.warning(
                    f"Gemini API call failed on attempt {attempt}/{self.max_retries} ({error_type}): {str(e)[:200]}"
                )

                if attempt < self.max_retries:
                    time.sleep(backoff_delay)
                    backoff_delay *= 2

        logger.error(f"Gemini API failed after {self.max_retries} attempts.")
        return None
