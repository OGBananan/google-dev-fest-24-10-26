from .vision import analyze_issue_photo
from .wards import find_ward
from .complaints import file_complaint, get_complaint_status

ALL_TOOLS = [analyze_issue_photo, find_ward, file_complaint, get_complaint_status]
