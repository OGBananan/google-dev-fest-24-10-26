# Civic Complaint Agent — Garbathon 2026

Build spec. Garbathon 2026 (GDG Ahmedabad), 24 Oct 2026. Solo, in-person, ~2h build.
Problem Statement 01 · Agents.

## The problem

Reporting a pothole, garbage, a broken streetlight or water logging means finding the
right ward and department, filing the complaint, then chasing it for weeks. Most people
give up before filing.

**Expected output (what the jury scores):** a photo goes in. The agent identifies the
issue, picks the ward and department, and files a complaint with a tracking ID. The user
asks "what's the status?" and gets an answer.

## Shape

Web app, not a chat box.

- **New complaint = a form.** Live camera capture + complaint text + auto-captured
  lat/lng. Submitting creates a new session; one session per complaint.
- **Follow-up = chat.** Once filed, the complaint view takes free-text questions
  ("what's the status?") against that complaint's session.

Form input is a feature, not a shortcut: it removes intent-parsing ambiguity and leaves
the agent doing the part that matters — classify the issue, judge severity, route to a
department, compose the complaint.

## Structure

Six-box agent model. Four boxes stay deliberately empty — at four tools and one linear
flow, subagents and skills are indirection with no demo benefit, and each is another
place the demo stalls in front of the jury.

| Box | This build |
|---|---|
| Schedule | — none. User-triggered, not recurring. |
| Channels | Web form + per-complaint chat. See "Surface". |
| Agent + Instructions | One `LlmAgent`. Ordering rules + no-invented-IDs constraint. |
| Toolbox | Four functions, below. |
| Sub-agents | — none. |
| Skills | — none. ADK has no first-class skills primitive; inline into the prompt. |

## Toolbox

```python
analyze_issue_photo(image_path: str) -> dict
    # {issue_type, severity, description}
    # Calls Gemini vision INTERNALLY. See "Vision stays inside the tool".

find_ward(lat=None, lng=None, area_name=None) -> dict
    # {ward, department, officer}  — lookup against wards.json
    # lat/lng -> nearest ward centroid. area_name -> string match fallback.

file_complaint(issue_type, ward, department, description) -> dict
    # {tracking_id}  — ONLY source of tracking IDs. Appends to wards.json.

get_complaint_status(tracking_id: str) -> dict
    # {status, filed_at, department}  — reads wards.json complaints[]
```

Only `analyze_issue_photo` touches a model. The rest are local lookups and file I/O.

### Location — browser geolocation, not EXIF

A `getUserMedia` canvas capture has **no EXIF at all** (fresh blob, no camera metadata).
So EXIF parsing is irrelevant here. Use `navigator.geolocation.getCurrentPosition()` and
pass lat/lng as a form field — live, accurate, no DMS conversion, nothing to strip.

Resolve lat/lng by **nearest ward centroid in `wards.json`**, not a live Geocoding call.
No API dependency, survives Wi-Fi failure, accurate enough at Ahmedabad ward scale.

Keep a typed area-name field as manual fallback. The problem statement sanctions both:
*"use the photo's location, or let the user type an area name."*

**Permission sequencing.** Camera and location are two independent prompts. Fire
`getCurrentPosition()` **on page load**, not at submit — a cold fix takes 5–20s and that
silence mid-demo reads as a hang. Request the camera when they tap capture.

**Indoors, GPS will not lock.** `enableHighAccuracy: true` waits for a satellite fix that
never arrives in a hall, then times out. Use WiFi/cell positioning instead:

```js
navigator.geolocation.getCurrentPosition(ok, fail, {
  enableHighAccuracy: false,   // WiFi/cell — fast indoors
  timeout: 8000,
  maximumAge: 300000           // accept a 5-min-old cached fix
});
```

Good enough to pick a ward, and the venue is in Ahmedabad — so the fix resolves to a
genuine ward and the demo story stays honest: *standing here, pothole here, routed to
this ward's Roads Dept.*

**Never let a failed fix block filing.** Render lat/lng as an **editable** field with the
area name beside it. Denied permission or timeout → user types "Navrangpura", flow
continues. A visible graceful fallback scores; a spinner does not.

> **Secure-context trap.** `getUserMedia` and `geolocation` both require HTTPS.
> `localhost` counts as secure; Cloud Run is HTTPS. **But a LAN IP
> (`http://192.168.x.x:8000`) is not** — both APIs fail silently there. If a phone is
> part of the demo, deploy to Cloud Run. Decide this early, not at 7pm.

### Vision stays inside the tool

The agent is **text-only**. The photo never enters the ADK turn as a multimodal part.
The form uploads the image, the backend saves it, `analyze_issue_photo` takes the path
and calls Gemini itself.

Mixing image parts into a turn that also needs function calling is the fiddliest part of
the stack, and routing around it costs nothing here.

### Show the tool trace

This is the Agents category. A form → result card reads as CRUD with a vision call bolted
on, and hides the thing being scored. Return the tool calls and their returns in the
response and render them as they land:

```
analyze_issue_photo  →  pothole, high severity
find_ward            →  Navrangpura, Roads Dept
file_complaint       →  AMC-2026-0412
```

~20 lines. It's what made `adk web` good theater; don't lose it by building a frontend.

## Data

- `wards.json` — mock AMC ward/department/officer table, each ward with a **centroid
  lat/lng**. Pre-geocoded. Do not call the Maps API live.
- `complaints.json` — written by `file_complaint`, read by `get_complaint_status`.

Mock the municipal system entirely. Per the rules: no real portal, and say so in the demo.

## Sessions

One ADK session per complaint. The session exists **before** the tracking ID does — the
ID only comes back from `file_complaint`. So generate a `session_id` (uuid) at form
submit and store the tracking ID against it when the tool returns.

## Guardrails (put in the system prompt)

1. **Never invent a tracking ID.** Only ever report an ID returned by `file_complaint`.
   Otherwise the agent confidently reports a plausible fake, `get_complaint_status` can't
   find it, and it breaks live.
2. Call tools in order: analyze → find ward → file → (later) status.
3. Never state a ward or department not returned by `find_ward`.
4. If no coordinates were supplied, **ask the user for the area name**. Do not guess a
   location from the image contents.

## Surface

ADK is the **framework**; `adk web` is only one bundled surface. Also available:
`adk run` (CLI), `adk api_server` (FastAPI REST), or embed `Runner` in your own app.
Nothing mandates the dev UI — the hackathon lists ADK as a suggested resource, and the
only hard rule is Google tech only.

This build: FastAPI wrapping ADK `Runner`, serving the static page from the same app.
Vanilla JS, no framework, no build step.

## Hosting — one Cloud Run service

Demoing from a phone, so the backend must be publicly reachable over HTTPS: the phone
can't reach laptop localhost, and an HTTPS page can't call plain HTTP.

Firebase Hosting is static-only (≈ S3 + CloudFront + ACM in one command) — it can't run
the Python backend. Putting the page there and the API on Cloud Run means two deploy
targets and CORS config, for no gain. Instead, serve both from one service:

```python
app.mount("/", StaticFiles(directory="public", html=True))
```

```bash
gcloud run deploy civic-agent --source . --allow-unauthenticated
```

`--source` uses Cloud Buildpacks — detects Python from `requirements.txt`, no Dockerfile.
One HTTPS URL, secure context satisfied, same-origin so no CORS.

> **Gate: Cloud Run requires billing enabled on the GCP project.** Free tier exists but a
> billing account must be attached. Do not discover this at 6pm.

### Prep before the clock starts

Toolchain and account setup, not project code:

1. Create the GCP project, **attach billing**.
2. `gcloud auth login`, `gcloud config set project <id>`, enable Cloud Run + Cloud Build.
3. Deploy a hello-world FastAPI with the exact command above — prove the toolchain.
4. **Open that URL on the phone.** Confirm camera + geolocation prompts fire.

Step 4 de-risks the entire demo surface before a line of the agent exists.

## Build order — backend first

Non-negotiable sequencing. Build and verify the backend with `adk run` or curl **before**
touching the frontend. That keeps `adk web` alive as a working, demoable fallback the
whole time. If the camera fights you at 7:15pm you still have an end-to-end complaint
flow to show. Do it the other way round and a frontend bug leaves you with nothing.

| | |
|---|---|
| Backend: 4 tools, runner, one endpoint | 40 min |
| Frontend: camera, geolocation, form, result card, tool trace | 45 min |
| Wiring + debug | 20 min |
| Record the demo | 10 min |

No slack. Hence the fallback.

Deploy early and often — once the hello-world is up, each redeploy is ~2 min. Test on the
phone at every stage rather than discovering a mobile-only bug at the end.

## Demo script

1. Open the deployed app on the phone.
2. Capture a photo of the pothole live, type the complaint, submit.
3. Jury watches the tool trace land: analyze → find_ward → file_complaint → tracking ID.
4. Ask "what's the status?" in the complaint view.

## Risks

- **Model access.** Make one trivial API call before building anything. `gemini-4-argon`
  is paid-tier only; if the key is free-tier it will 403. Drop to a model the key can
  actually reach — nothing here is Argon-specific.
- **ADK setup cost.** `Runner` + `SessionService` + `types.Content` boilerplate is
  non-obvious. If the first tool call hasn't fired within ~30 min, fall back to a plain
  Gemini function-calling loop with the same four tools. Tenth of the setup surface.
- **Secure context.** See the trap above. Deploy early if demoing from a phone.
- **Wi-Fi.** Once a run works, screen-record it immediately. Per the rules, a recording
  of the live run scores the same as a live demo.

## Out of scope

Optional social-media post drafting (photo + tracking ID + tags for the city corporation
and local ward). Only if ahead of schedule.

## Constraints

- Google tech only: Gemini, AI Studio, Antigravity, Firebase, Google Cloud, Maps Platform.
  Public datasets from anywhere are fine.
- Solo. Built during the event — pre-built projects are not eligible.
- Demo first. Judges score the working flow, not slides.
- Cut scope, not polish. One flow end to end beats three half-built features.
