from datetime import datetime, time, date
from pydantic import BaseModel

class Employee(BaseModel):
    id: int
    badge_id: str
    is_active: bool
    shift_start_time: time
    shift_end_time: time

class Punch(BaseModel):
    employee_id: int
    punch_type: str
    timestamp: datetime
    is_late: bool = False
    lateness_minutes: int = 0
    is_early: bool = False
    earliness_minutes: int = 0

class OvertimeApproval(BaseModel):
    employee_id: int
    date: date
    is_approved: bool

class WorkHoursSummary(BaseModel):
    work_hours: float
    break_hours: float
    overtime_hours: float
