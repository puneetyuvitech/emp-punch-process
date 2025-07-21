import logging
from datetime import datetime
from typing import Optional, Dict

from utils.helper import get_employee_by_badge, get_last_punch, insert_punch, get_overtime_approval, get_all_punches_for_day, get_employee_shift_time

TIME_WINDOW_MINUTES = 10

def is_end_of_day(timestamp: datetime) -> bool:
    return timestamp.hour == 23 and timestamp.minute >= 59

def check_for_missing_punch_out(employee, timestamp):
    last_punch = get_last_punch(employee.id, timestamp.date())
    if last_punch and last_punch.punch_type in ["IN", "BREAK_IN", "OVERTIME_IN"]:
        defaulter_punch = {
            "employee_id": employee.id,
            "punch_type": "DEFAULTER",
            "timestamp": timestamp,
            "is_late": False,
            "lateness_minutes": 0,
            "is_early": False,
            "earliness_minutes": 0
        }
        insert_punch(defaulter_punch)
        logging.warning(f"Defaulter punch recorded for employee_id: {employee.id}")


def determine_punch_type(employee, timestamp: datetime) -> Dict:
    punch_minutes = timestamp.hour * 60 + timestamp.minute
    shift_start = employee.shift_start_time
    shift_end = employee.shift_end_time
    start_minutes = shift_start.hour * 60 + shift_start.minute
    end_minutes = shift_end.hour * 60 + shift_end.minute

    result = {
        "type": "UNKNOWN",
        "is_late": False,
        "lateness_minutes": 0,
        "is_early": False,
        "earliness_minutes": 0
    }

    if abs(punch_minutes - start_minutes) <= TIME_WINDOW_MINUTES:
        result["type"] = "IN"
    elif punch_minutes > start_minutes + TIME_WINDOW_MINUTES:
        result["type"] = "LATE_IN"
        result["is_late"] = True
        result["lateness_minutes"] = punch_minutes - start_minutes
    elif abs(punch_minutes - end_minutes) <= TIME_WINDOW_MINUTES:
        result["type"] = "OUT"
    elif punch_minutes < end_minutes - TIME_WINDOW_MINUTES:
        result["type"] = "OUT"
        result["is_early"] = True
        result["earliness_minutes"] = end_minutes - punch_minutes
    elif start_minutes < punch_minutes < end_minutes:
        last_punch = get_last_punch(employee.id, timestamp.date())
        if last_punch and last_punch.punch_type in ["IN", "BREAK_IN"]:
            result["type"] = "BREAK_OUT"
        else:
            result["type"] = "BREAK_IN"
    elif punch_minutes > end_minutes + TIME_WINDOW_MINUTES:
        last_punch = get_last_punch(employee.id, timestamp.date())
        if last_punch and last_punch.punch_type in ["OUT", "BREAK_OUT"]:
            result["type"] = "OVERTIME_IN"
        else:
            result["type"] = "OVERTIME_OUT"

    return result


def process_punch(badge_id: str, timestamp: datetime) -> Optional[Dict]:
    employee = get_employee_by_badge(badge_id)
    if not employee or not employee.is_active:
        logging.error(f"Unknown or inactive badge ID: {badge_id}")
        return None

    punch_info = determine_punch_type(employee, timestamp)
    punch_type = punch_info["type"]

    last_punch = get_last_punch(employee.id, timestamp.date())
    if last_punch:
        if last_punch.punch_type in ["IN", "BREAK_IN", "OVERTIME_IN"] and punch_type in ["IN", "BREAK_IN", "OVERTIME_IN"]:
            logging.warning(f"Duplicate IN-type punch for employee_id: {employee.id}")
            return None
        if last_punch.punch_type in ["OUT", "BREAK_OUT", "OVERTIME_OUT"] and punch_type in ["OUT", "BREAK_OUT", "OVERTIME_OUT"]:
            logging.warning(f"Duplicate OUT-type punch for employee_id: {employee.id}")
            return None

    if punch_type in ["OVERTIME_IN", "OVERTIME_OUT"]:
        approval = get_overtime_approval(employee.id, timestamp.date())
        if not approval:
            logging.warning(f"Unapproved overtime for employee_id: {employee.id}")
            return None

    new_punch = {
        "employee_id": employee.id,
        "punch_type": punch_type,
        "timestamp": timestamp,
        "is_late": punch_info["is_late"],
        "lateness_minutes": punch_info["lateness_minutes"],
        "is_early": punch_info["is_early"],
        "earliness_minutes": punch_info["earliness_minutes"]
    }
    insert_punch(new_punch)

    if is_end_of_day(timestamp):
        check_for_missing_punch_out(employee, timestamp)

    return new_punch


def calculate_work_hours(employee_id: int, date: datetime.date) -> Dict:
    punches = get_all_punches_for_day(employee_id, date)
    total_work = total_break = total_overtime = 0.0
    last_in = None
    last_type = None

    for punch in punches:
        if punch.punch_type in ["IN", "BREAK_IN", "OVERTIME_IN"]:
            last_in = punch.timestamp
            last_type = punch.punch_type
        elif punch.punch_type in ["OUT", "BREAK_OUT", "OVERTIME_OUT"] and last_in:
            duration = (punch.timestamp - last_in).total_seconds() / 3600.0
            if last_type == "OVERTIME_IN":
                total_overtime += duration
            else:
                total_work += duration
            last_in = None
            last_type = None
        elif punch.punch_type == "DEFAULTER" and last_in:
            shift_end = get_employee_shift_time(employee_id)["end"]
            shift_end_time = datetime.combine(date, shift_end)
            duration = (shift_end_time - last_in).total_seconds() / 3600.0
            total_work += duration
            last_in = None
            last_type = None

    for i in range(len(punches) - 1):
        if punches[i].punch_type == "BREAK_OUT" and punches[i+1].punch_type == "BREAK_IN":
            break_duration = (punches[i+1].timestamp - punches[i].timestamp).total_seconds() / 3600.0
            total_break += break_duration

    return {
        "work_hours": round(total_work, 2),
        "break_hours": round(total_break, 2),
        "overtime_hours": round(total_overtime, 2)
    }
