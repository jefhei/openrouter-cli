"""
Mock data fixtures for OpenRouter CLI tests.

Load mock responses using:
    from tests.mocks import load_mock
    
    data = load_mock("models_list.json")
"""

import json
from pathlib import Path

MOCKS_DIR = Path(__file__).parent


def load_mock(filename: str) -> dict:
    """Load a mock JSON file."""
    mock_path = MOCKS_DIR / filename
    if not mock_path.exists():
        raise FileNotFoundError(f"Mock file not found: {filename}")
    return json.loads(mock_path.read_text())


def load_error_response(error_type: str) -> dict:
    """Load a specific error response from error_responses.json."""
    errors = load_mock("error_responses.json")
    if error_type not in errors:
        raise KeyError(f"Unknown error type: {error_type}")
    return errors[error_type]
