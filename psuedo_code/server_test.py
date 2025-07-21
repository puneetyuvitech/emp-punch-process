TEST test_valid_employee_punch_in_on_time:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    SET timestamp = 2025-07-21 09:05
    punch = CALL system.process_punch("12345", timestamp)
    ASSERT punch.punch_type = "IN"
    ASSERT punch.is_late = FALSE
    ASSERT SQL "INSERT INTO Punch ..." WAS CALLED WITH punch_type = "IN"

TEST test_valid_employee_punch_in_late:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    SET timestamp = 2025-07-21 09:30
    punch = CALL system.process_punch("12345", timestamp)
    ASSERT punch.punch_type = "LATE_IN"
    ASSERT punch.is_late = TRUE
    ASSERT punch.lateness_minutes = 30
    ASSERT SQL "INSERT INTO Punch ..." WAS CALLED WITH punch_type = "LATE_IN"

TEST test_valid_employee_punch_out_early:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    SET timestamp = 2025-07-21 16:30
    punch = CALL system.process_punch("12345", timestamp)
    ASSERT punch.punch_type = "OUT"
    ASSERT punch.is_early = TRUE
    ASSERT punch.earliness_minutes = 30
    ASSERT SQL "INSERT INTO Punch ..." WAS CALLED WITH punch_type = "OUT"

TEST test_break_punch_sequence:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    MOCK SQL "SELECT * FROM Punch ..." TO RETURN RECORD WITH punch_type = "IN"
    SET timestamp = 2025-07-21 12:00
    punch = CALL system.process_punch("12345", timestamp)
    ASSERT punch.punch_type = "BREAK_OUT"
    ASSERT SQL "INSERT INTO Punch ..." WAS CALLED WITH punch_type = "BREAK_OUT"

TEST test_overtime_punch_approved:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    MOCK SQL "SELECT * FROM OvertimeApproval ..." TO RETURN RECORD WITH is_approved = TRUE
    SET timestamp = 2025-07-21 17:30
    MOCK SQL "SELECT * FROM Punch ..." TO RETURN RECORD WITH punch_type = "OUT"
    punch = CALL system.process_punch("12345", timestamp)
    ASSERT punch.punch_type = "OVERTIME_IN"
    ASSERT SQL "INSERT INTO Punch ..." WAS CALLED WITH punch_type = "OVERTIME_IN"

TEST test_overtime_punch_unapproved:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    MOCK SQL "SELECT * FROM OvertimeApproval ..." TO RETURN NULL
    SET timestamp = 2025-07-21 17:30
    MOCK SQL "SELECT * FROM Punch ..." TO RETURN RECORD WITH punch_type = "OUT"
    punch = CALL system.process_punch("12345", timestamp)
    ASSERT punch IS NULL
    ASSERT SQL "INSERT INTO Punch ..." WAS NOT CALLED

TEST test_duplicate_in_punch:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    MOCK SQL "SELECT * FROM Punch ..." TO RETURN RECORD WITH punch_type = "IN"
    SET timestamp = 2025-07-21 09:10
    punch = CALL system.process_punch("12345", timestamp)
    ASSERT punch IS NULL
    ASSERT SQL "INSERT INTO Punch ..." WAS NOT CALLED
    ASSERT ALERT_ADMIN WAS CALLED WITH "Duplicate IN-type punch"

TEST test_invalid_employee:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN NULL
    SET timestamp = 2025-07-21 09:00
    punch = CALL system.process_punch("99999", timestamp)
    ASSERT punch IS NULL
    ASSERT SQL "INSERT INTO Punch ..." WAS NOT CALLED
    ASSERT ALERT_ADMIN WAS CALLED WITH "Unknown badge ID"

TEST test_defaulter_punch_at_end_of_day:
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    MOCK SQL "SELECT * FROM Punch ..." TO RETURN RECORD WITH punch_type = "IN"
    MOCK system.is_end_of_day TO RETURN TRUE
    SET timestamp = 2025-07-21 23:59
    CALL system.process_punch("12345", timestamp)
    ASSERT SQL "INSERT INTO Punch ..." WAS CALLED WITH punch_type = "DEFAULTER"
    ASSERT ALERT_ADMIN WAS CALLED WITH "Missing OUT punch"

TEST test_calculate_work_break_overtime_hours:
    MOCK punches = [
        RECORD(type="IN", timestamp=2025-07-21 09:00),
        RECORD(type="BREAK_OUT", timestamp=2025-07-21 12:00),
        RECORD(type="BREAK_IN", timestamp=2025-07-21 13:00),
        RECORD(type="OUT", timestamp=2025-07-21 17:00),
        RECORD(type="OVERTIME_IN", timestamp=2025-07-21 17:30),
        RECORD(type="OVERTIME_OUT", timestamp=2025-07-21 19:30)
    ]
    MOCK SQL "SELECT * FROM Employee ..." TO RETURN mock_employee
    MOCK SQL "SELECT * FROM Punch ..." TO RETURN punches
    result = CALL system.calculate_work_hours(1, 2025-07-21)
    ASSERT result.work_hours = 7.0  
    ASSERT result.break_hours = 1.0  
    ASSERT result.overtime_hours = 2.0  