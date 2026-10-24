"""TOOLBOX — complaint filing and status.

file_complaint is the ONLY source of tracking IDs. The agent is forbidden from
inventing one; if it did, get_complaint_status would fail live in front of the
jury.
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
