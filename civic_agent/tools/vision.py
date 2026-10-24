"""TOOLBOX — vision.

The agent is text-only. The photo never enters the ADK turn as a multimodal
part: the form uploads it, the backend saves it, and this tool calls Gemini
itself with the file path.
"""

import mimetypes
import os
from pathlib import Path

from google import genai
from google.genai import types

MODEL = os.getenv("GEMINI_MODEL", "gemini-4-argon")

# Must match the keys in wards.json -> departments, or routing KeyErrors.
ISSUE_TYPES = ["pothole", "garbage", "streetlight", "waterlogging", "other"]

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "issue_type": {"type": "STRING", "enum": ISSUE_TYPES},
        "severity": {"type": "STRING", "enum": ["low", "medium", "high"]},
        "description": {"type": "STRING"},
    },
    "required": ["issue_type", "severity", "description"],
}

_PROMPT = (
    "You are triaging a civic complaint photo for an Indian municipal corporation. "
    "Classify the primary issue visible. Use 'other' if it is not one of the listed "
    "civic issues. Judge severity by public risk: blocking traffic, injury risk or "
    "standing water is high. Write the description as one factual sentence an "
    "official would read - no speculation about who is at fault."
)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return _client


def analyze_issue_photo(image_path: str) -> dict:
    """Identify the civic issue in a photo.

    Args:
        image_path: Path to the uploaded photo on disk.

    Returns:
        issue_type (pothole, garbage, streetlight, waterlogging or other),
        severity (low, medium, high) and a one-sentence description.
    """
    path = Path(image_path)
    if not path.is_file():
        return {"error": f"no file at {image_path}"}

    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    resp = _get_client().models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=path.read_bytes(), mime_type=mime),
            _PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_SCHEMA,
        ),
    )
    import json

    return json.loads(resp.text)
