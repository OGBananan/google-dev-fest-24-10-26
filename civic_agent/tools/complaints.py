"""TOOLBOX — filing and status lookup against the mocked AMC system.

Per the hackathon rules the municipal side is mocked as local JSON; no real AMC portal
is contacted. ``wards.json`` holds the ward table, the department map and the complaint
records together, so the whole data layer stays inspectable during the demo.

``file_complaint`` is the ONLY source of tracking IDs, and the agent's system prompt
forbids inventing one. If it invented an ID, ``get_complaint_status`` would fail to find
it live in front of the jury.
"""

from ..data import load, mutate, now_ist


def _next_tracking_id(db: dict) -> str:
    existing = [c["trackingId"] for c in db.get("complaints", [])]
    seq = max((int(t.rsplit("-", 1)[-1]) for t in existing if t.rsplit("-", 1)[-1].isdigit()), default=0)
    return f"AMC-2026-{seq + 1:06d}"


def file_complaint(
    issue_type: str,
    ward_id: str,
    department: str,
    description: str,
) -> dict:
    """File the complaint with the municipal corporation and get a tracking ID.

    Call this only after analyze_issue_photo and find_ward have both returned.

    Args:
        issue_type: pothole, garbage, streetlight, waterlogging or other.
        ward_id: Ward id returned by find_ward, e.g. W12.
        department: Department returned by find_ward.
        description: One or two sentences describing the issue for the official.

    Returns:
        The tracking id, status and filing timestamp.
    """

    def _apply(db):
        record = {
            "trackingId": _next_tracking_id(db),
            "ward": ward_id,
            "issue": issue_type,
            "department": department,
            "description": description,
            "status": "Filed",
            "filedAt": now_ist(),
        }
        db.setdefault("complaints", []).append(record)
        return record

    record = mutate(_apply)
    return {
        "tracking_id": record["trackingId"],
        "status": record["status"],
        "filed_at": record["filedAt"],
    }


def get_complaint_status(tracking_id: str) -> dict:
    """Look up the current status of an already-filed complaint.

    Args:
        tracking_id: The tracking id, e.g. AMC-2026-000123.

    Returns:
        status, filed_at, department and ward for that complaint.
    """
    db = load()
    wanted = tracking_id.strip().upper()
    for c in db.get("complaints", []):
        if c["trackingId"].upper() == wanted:
            ward = next((w for w in db["wards"] if w["id"] == c["ward"]), None)
            return {
                "tracking_id": c["trackingId"],
                "status": c["status"],
                "filed_at": c["filedAt"],
                "issue_type": c["issue"],
                "department": c.get("department")
                or db["departments"].get(c["issue"], "General Complaints"),
                "ward_name": ward["name"] if ward else c["ward"],
            }
    return {"error": f"no complaint found with tracking id {tracking_id}"}


def list_existing_tickets(query: str = "", status: str = "") -> dict:
    """Find already filed tickets by issue, ward, tracking ID, or status.

    Args:
        query: Optional word or phrase to match against ticket ID, issue, ward, or description.
        status: Optional status to filter by, such as Filed, Assigned, or open.
            Use open to include all statuses except Resolved and Closed.

    Returns:
        Matching ticket summaries, newest first. Never creates a ticket.
    """
    db = load()
    ward_names = {w["id"]: w["name"] for w in db["wards"]}
    needle = query.strip().lower()
    wanted_status = status.strip().lower()
    matches = []
    for c in reversed(db.get("complaints", [])):
        ward_name = ward_names.get(c["ward"], c["ward"])
        searchable = " ".join(str(x) for x in (
            c["trackingId"], c["issue"], ward_name, c.get("description", "")
        )).lower()
        if needle and needle not in searchable:
            continue
        if wanted_status == "open" and c["status"].lower() in {"resolved", "closed"}:
            continue
        if wanted_status and wanted_status != "open" and wanted_status not in c["status"].lower():
            continue
        matches.append({
            "tracking_id": c["trackingId"],
            "issue_type": c["issue"],
            "ward_name": ward_name,
            "department": c.get("department", ""),
            "status": c["status"],
            "filed_at": c["filedAt"],
        })
    return {"tickets": matches[:20], "shown": min(len(matches), 20),
            "total": len(matches)}
