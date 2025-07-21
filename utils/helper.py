from typing import Optional, List
from datetime import date, time

# Mock employee and punch data stores
mock_employees = [
    {
        "id": 1,
        "badge_id": "123456",
        "is_active": True,
        "shift_start_time": time(9, 0),
        "shift_end_time": time(17, 0)
    }
]

mock_punches = []
mock_overtime_approvals = [
    {
        "employee_id": 1,
        "date": date.today(),
        "is_approved": True
    }
]

def get_employee_by_badge(badge_id: str) -> Optional[object]:
    for emp in mock_employees:
        if emp["badge_id"] == badge_id:
            return emp
    return None

def get_last_punch(employee_id: int, punch_date: date) -> Optional[object]:
    punches = [p for p in mock_punches if p["employee_id"] == employee_id and p["timestamp"].date() == punch_date]
    if punches:
        return sorted(punches, key=lambda x: x["timestamp"], reverse=True)[0]
    return None

def insert_punch(punch: dict) -> None:
    mock_punches.append(punch)

def get_overtime_approval(employee_id: int, punch_date: date) -> Optional[object]:
    for approval in mock_overtime_approvals:
        if approval["employee_id"] == employee_id and approval["date"] == punch_date and approval["is_approved"]:
            return approval
    return None

def get_all_punches_for_day(employee_id: int, punch_date: date) -> List[object]:
    return sorted([
        p for p in mock_punches if p["employee_id"] == employee_id and p["timestamp"].date() == punch_date
    ], key=lambda x: x["timestamp"])

def get_employee_shift_time(employee_id: int) -> dict:
    for emp in mock_employees:
        if emp["id"] == employee_id:
            return {
                "start": emp["shift_start_time"],
                "end": emp["shift_end_time"]
            }
    return {"start": time(9, 0), "end": time(17, 0)}
