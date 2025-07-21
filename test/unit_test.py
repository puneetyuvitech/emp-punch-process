import pytest
from datetime import datetime, timedelta, time, date
from main import process_punch, calculate_work_hours
from utils.helper import mock_employees, mock_punches, mock_overtime_approvals

def setup_function():
    mock_punches.clear()

def test_regular_in_and_out():
    badge_id = "123456"
    in_time = datetime.combine(date.today(), time(9, 0))
    out_time = datetime.combine(date.today(), time(17, 0))

    punch_in = process_punch(badge_id, in_time)
    punch_out = process_punch(badge_id, out_time)

    assert punch_in is not None
    assert punch_in["punch_type"] == "IN"

    assert punch_out is not None
    assert punch_out["punch_type"] == "OUT"

    summary = calculate_work_hours(punch_in["employee_id"], in_time.date())
    assert summary["work_hours"] == 8.0
    assert summary["break_hours"] == 0.0
    assert summary["overtime_hours"] == 0.0

def test_late_in():
    badge_id = "123456"
    late_in_time = datetime.combine(date.today(), time(9, 15))

    punch = process_punch(badge_id, late_in_time)

    assert punch is not None
    assert punch["punch_type"] == "LATE_IN"
    assert punch["is_late"] is True
    assert punch["lateness_minutes"] == 15

def test_early_out():
    badge_id = "123456"
    process_punch(badge_id, datetime.combine(date.today(), time(9, 0)))
    early_out_time = datetime.combine(date.today(), time(16, 30))

    punch = process_punch(badge_id, early_out_time)

    assert punch is not None
    assert punch["punch_type"] == "OUT"
    assert punch["is_early"] is True
    assert punch["earliness_minutes"] == 30

def test_duplicate_in():
    badge_id = "123456"
    t1 = datetime.combine(date.today(), time(9, 0))
    t2 = t1 + timedelta(minutes=5)

    punch1 = process_punch(badge_id, t1)
    punch2 = process_punch(badge_id, t2)

    assert punch1 is not None
    assert punch2 is None  

def test_overtime_without_approval():
    badge_id = "123456"
    in_time = datetime.combine(date.today(), time(9, 0))
    process_punch(badge_id, in_time)

    mock_overtime_approvals.clear()

    overtime_out_time = datetime.combine(date.today(), time(18, 30))
    punch = process_punch(badge_id, overtime_out_time)
    assert punch is None

def test_overtime_with_approval():
    badge_id = "123456"
    in_time = datetime.combine(date.today(), time(9, 0))
    process_punch(badge_id, in_time)

    overtime_in_time = datetime.combine(date.today(), time(17, 10))
    overtime_out_time = datetime.combine(date.today(), time(19, 0))

    process_punch(badge_id, overtime_in_time)
    process_punch(badge_id, overtime_out_time)

    summary = calculate_work_hours(1, date.today())
    assert summary["overtime_hours"] == 1.83
