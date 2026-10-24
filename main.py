"""CHANNELS — the only surface.

A web form creates a new complaint (one ADK session each); the complaint view
then takes free-text follow-ups against that same session. Static page is
served from this app so there is one origin, one deploy and no CORS.
"""

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from civic_agent.agent import root_agent
from civic_agent.data import load

APP_NAME = "civic_agent"
USER_ID = "resident"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Civic Complaint Agent")
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

# session_id -> tracking_id. The session exists before the ID does; the ID only
# comes back from file_complaint.
SESSION_TRACKING: dict[str, str] = {}


async def _run(session_id: str, message: str) -> dict:
    """Send one message to the agent, return its reply plus the tool trace."""
    trace: list[dict] = []
    reply_parts: list[str] = []

    content = types.Content(role="user", parts=[types.Part(text=message)])
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=content
    ):
        parts = getattr(getattr(event, "content", None), "parts", None) or []
        for part in parts:
            call = getattr(part, "function_call", None)
            if call is not None:
                trace.append({"kind": "call", "name": call.name, "args": dict(call.args or {})})
            resp = getattr(part, "function_response", None)
            if resp is not None:
                trace.append({"kind": "result", "name": resp.name, "data": dict(resp.response or {})})
        if event.is_final_response():
            for part in parts:
                if getattr(part, "text", None):
                    reply_parts.append(part.text)

    # file_complaint is the only source of tracking IDs - pick it out of the trace.
    for step in trace:
        if step["kind"] == "result" and step["name"] == "file_complaint":
            tid = step["data"].get("tracking_id")
            if tid:
                SESSION_TRACKING[session_id] = tid

    return {
        "reply": "\n".join(reply_parts).strip(),
        "trace": trace,
        "tracking_id": SESSION_TRACKING.get(session_id),
    }


@app.post("/api/complaints")
async def create_complaint(
    photo: UploadFile = File(...),
    description: str = Form(""),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    area_name: str = Form(""),
):
    session_id = uuid.uuid4().hex
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )

    suffix = Path(photo.filename or "capture.jpg").suffix or ".jpg"
    saved = UPLOAD_DIR / f"{session_id}{suffix}"
    saved.write_bytes(await photo.read())

    where = (
        f"coordinates lat={lat}, lng={lng}"
        if lat is not None and lng is not None
        else f"area name '{area_name}'" if area_name else "no location supplied"
    )
    message = (
        f"File a new complaint.\n"
        f"Photo path: {saved}\n"
        f"Location: {where}\n"
        f"What the resident said: {description or '(nothing typed)'}"
    )

    result = await _run(session_id, message)
    return JSONResponse({"session_id": session_id, **result})


async def _ensure_session(session_id: str) -> None:
    existing = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )
    if existing is None:
        await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )


@app.post("/api/complaints/{session_id}/chat")
async def chat(session_id: str, payload: dict):
    """Follow-up inside the session that filed a specific complaint."""
    message = (payload or {}).get("message", "").strip()
    if not message:
        raise HTTPException(400, "message is required")
    await _ensure_session(session_id)
    return JSONResponse(await _run(session_id, message))


@app.post("/api/chat")
async def general_chat(payload: dict):
    """Standalone status chat, not tied to filing anything.

    The client keeps its own session id so the thread survives reloads;
    the session is created on first use.
    """
    payload = payload or {}
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message is required")
    session_id = (payload.get("session_id") or "").strip() or f"chat-{uuid.uuid4().hex}"
    await _ensure_session(session_id)
    result = await _run(session_id, message)
    return JSONResponse({"session_id": session_id, **result})


@app.get("/api/complaints")
async def list_complaints():
    db = load()
    wards = {w["id"]: w["name"] for w in db["wards"]}
    return [
        {**c, "wardName": wards.get(c["ward"], c["ward"])}
        for c in reversed(db.get("complaints", []))
    ]


app.mount("/", StaticFiles(directory="public", html=True), name="public")
