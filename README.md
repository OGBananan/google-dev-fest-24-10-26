# Civic Complaint Agent

**Garbathon 2026 · GDG Ahmedabad · Problem Statement 01 — Agents**

Photograph a pothole. The agent identifies the issue, works out which AMC ward owns that
street and which department handles that kind of problem, files the complaint, and hands
back a tracking ID. Ask it the status later in plain language.

Reporting a civic issue in India means finding the right ward, finding the right
department, filing, and then chasing for weeks. Most people give up before they file.
This collapses that into one photo and one sentence.

---

## Demo

| Landing | Agent working | Status |
|---|---|---|
| ![Landing](docs/01-landing.png) | ![Agent trace](docs/02-trace.png) | ![Status chat](docs/03-status.png) |

> Replace the three files in `docs/` with your own screenshots.

---

## What it does

1. **Capture** — live camera in the browser, coordinates from the Geolocation API
2. **Classify** — Gemini identifies the issue type and rates severity by public risk
3. **Route** — coordinates resolve to the nearest AMC ward, then to the owning department
4. **File** — a tracking ID is minted and persisted
5. **Follow up** — ask about any ticket by ID, in plain language

Every tool call and its return is rendered on screen as it happens, with timings. Tap
any call for the raw JSON. The point of the Agents category is that the model decides
the sequence — so the app shows the sequence rather than hiding it.

---

## Built with Google

| Layer | Technology |
|---|---|
| Agent runtime | **Google Agent Development Kit (ADK)** — `LlmAgent`, `Runner`, `InMemorySessionService` |
| Reasoning + vision | **Gemini** (`gemini-3-flash-preview`, set via `GEMINI_MODEL`) |
| Tool schemas | **ADK automatic function calling** — schemas derived from type hints and docstrings |
| Image understanding | **Gemini multimodal** with **structured output** (`response_schema` + enum) |
| Location | **Browser Geolocation API**, resolved against pre-geocoded ward centroids |
| Hosting | **Cloud Run** — `gcloud run deploy --source .`, Cloud Buildpacks, no Dockerfile |
| IDE | **Google Antigravity** |

No non-Google AI, tooling or hosting is used in the running product.

---

## Architecture

The agent is structured as five concerns, four tools, and one surface:

```
civic_agent/
  agent.py              AGENT + INSTRUCTIONS   one LlmAgent, ordering rules, guardrails
  tools/
    vision.py           TOOLBOX  analyze_issue_photo   (Gemini vision + structured output)
    wards.py            TOOLBOX  find_ward             (nearest centroid → department)
    complaints.py       TOOLBOX  file_complaint, get_complaint_status
  data.py               mocked AMC store (atomic JSON read-modify-write)
main.py                 CHANNELS  FastAPI + ADK Runner + static page
public/index.html       the app — vanilla JS, no framework, no build step
wards.json              15 wards, 116 area names, departments, complaint records
```

There are deliberately **no sub-agents and no skills**. At four tools and one linear
flow they would be indirection with no benefit, and each one is another place a live
demo can stall.

### Guardrails

The system prompt enforces three rules that matter more than they look:

- **Never invent a tracking ID.** Only an ID returned by `file_complaint` may be stated.
  Otherwise the agent reports a plausible fake and the status lookup fails on stage.
- **Never state a ward or department `find_ward` didn't return.**
- **If the location is unknown, ask** — don't guess a location from the photo contents.

---

## Running it

```bash
pip install -r requirements.txt
echo "GOOGLE_API_KEY=your-key" > .env
echo "GEMINI_MODEL=gemini-3-flash-preview" >> .env
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. `localhost` counts as a secure context, so camera and
geolocation both work without HTTPS.

### Deploy

```bash
gcloud run deploy civic-agent --source . --allow-unauthenticated
```

One service serves the API and the page — same origin, no CORS, HTTPS included, which
is what the camera and geolocation APIs require on a phone.

---

## Resilience

Built for a room with bad Wi-Fi and a free-tier API key:

- **Quota or model outage** → a cached recording of the same flow is served instead of a
  500, clearly labelled **"cached run"** on screen and flagged `meta.cached` in the API.
  The rules give cached responses full credit; this is never passed off as live.
- **Geolocation denied or timed out** → the typed area field takes over, and 116 area
  names resolve to a ward.
- **Indoors** → `enableHighAccuracy: false` so it uses WiFi positioning instead of
  waiting on a GPS fix that will not lock inside a hall.

---

## Mocking

Per the hackathon rules, the municipal side is **mocked as local JSON** — no real AMC
portal is contacted, no municipal login, no third-party API. `wards.json` holds the ward
table, the department map and the complaint records together.

Ward IDs are invented; centroids are approximate (±500m), which is well within tolerance
for nearest-centroid routing at ward scale.

---

## Datasets

Used for testing the classifier, not for training — Gemini classifies zero-shot.

- [Urban Civic Issues: Potholes and Garbage (QR4Change)](https://data.mendeley.com/datasets/zndzygc3p3/2) — CC BY 4.0, Pune
- [Pothole dataset](https://universe.roboflow.com/brad-dwyer/pothole-voxrl) — Roboflow Universe
