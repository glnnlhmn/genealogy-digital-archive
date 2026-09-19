# Name: test_gemini_client.py
# Path: tests/test_gemini_client.py

import os
import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel, Field
from tools.lib.gemini_client import GeminiClientWrapper

class SampleFact(BaseModel):
    event: str = Field(description="Event name")
    year: int = Field(description="Event year")

def test_missing_api_key_raises_error():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
            GeminiClientWrapper()

@patch("tools.lib.gemini_client.genai.Client")
def test_successful_structured_extraction(mock_genai_client):
    mock_response = MagicMock()
    mock_response.text = '{"event": "Birth", "year": 1882}'
    
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    wrapper = GeminiClientWrapper(api_key="mock_key")
    result = wrapper.extract_structured(
        prompt="Sample record",
        response_schema=SampleFact,
        models=["gemini-3.8-flash"]
    )

    assert isinstance(result, SampleFact)
    assert result.event == "Birth"
    assert result.year == 1882

@patch("tools.lib.gemini_client.genai.Client")
def test_fallback_on_503_capacity_issue(mock_genai_client):
    mock_client_instance = MagicMock()
    
    # 503 on gemini-3.8-flash (attempt 1 and 2), success on gemini-3.6-flash
    mock_success = MagicMock()
    mock_success.text = '{"event": "Death", "year": 1945}'
    
    mock_client_instance.models.generate_content.side_effect = [
        RuntimeError("503 UNAVAILABLE"),
        RuntimeError("503 UNAVAILABLE"),
        mock_success
    ]
    mock_genai_client.return_value = mock_client_instance

    wrapper = GeminiClientWrapper(api_key="mock_key")
    result = wrapper.extract_structured(
        prompt="Sample record",
        response_schema=SampleFact,
        models=["gemini-3.8-flash", "gemini-3.6-flash"],
        backoff_seconds=0.01
    )

    assert result.event == "Death"
    assert result.year == 1945
    assert mock_client_instance.models.generate_content.call_count == 3

@pytest.mark.integration
def test_live_api_extraction():
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not found in environment.")
    
    wrapper = GeminiClientWrapper()
    result = wrapper.extract_structured(
        prompt="Jacob Lehman passed away in 1904 in Lancaster.",
        response_schema=SampleFact
    )
    assert result.event != ""
    assert result.year == 1904