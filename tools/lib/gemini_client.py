# Name: gemini_client.py
# Path: tools/lib/gemini_client.py

import os
import time
from typing import Type, TypeVar, Optional, List
from pydantic import BaseModel
from google import genai
from google.genai import types

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite"
]

class GeminiClientWrapper:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.client = genai.Client(api_key=self.api_key)

    def extract_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str = "You are an archival extraction engine. Adhere strictly to date conservatism.",
        models: Optional[List[str]] = None,
        max_attempts_per_model: int = 2,
        backoff_seconds: float = 3.0
    ) -> T:
        candidate_models = models or DEFAULT_MODELS
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            system_instruction=system_instruction
        )

        last_error = None
        for model_name in candidate_models:
            for attempt in range(1, max_attempts_per_model + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    if not response.text:
                        raise ValueError(f"Empty response returned by {model_name}")
                    return response_schema.model_validate_json(response.text)
                except Exception as exc:
                    err_msg = str(exc)
                    last_error = exc
                    if "503" in err_msg or "429" in err_msg:
                        if attempt < max_attempts_per_model:
                            time.sleep(backoff_seconds)
                            continue
                    break

        raise RuntimeError(f"All candidate models failed structured extraction. Last error: {last_error}")