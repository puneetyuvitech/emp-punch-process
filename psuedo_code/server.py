ASYNC FUNCTION process_punch(badge_id, timestamp):
    # Database Flow: Query Employee table to find employee
    employee = EXECUTE SQL "SELECT * FROM Employee WHERE badge_id = :badge_id" WITH badge_id
    IF employee IS NULL OR NOT employee.is_active:
        LOG "Unknown or inactive badge ID: badge_id"
        ALERT_ADMIN "Unknown badge ID detected"
        RETURN NULL

    # Database Flow: Check last punch to detect duplicate/invalid punches
    last_punch = EXECUTE SQL "SELECT * FROM Punch WHERE employee_id = :employee_id AND DATE(timestamp) = :date ORDER BY timestamp DESC LIMIT 1" 
                 WITH employee.id, timestamp.date
    IF last_punch EXISTS:
        IF last_punch.punch_type IN ["IN", "BREAK_IN", "OVERTIME_IN"] AND punch_type IN ["IN", "BREAK_IN", "OVERTIME_IN"]:
            LOG "Duplicate IN-type punch detected"
            ALERT_ADMIN "Duplicate IN-type punch for employee_id: employee.id"
            RETURN NULL
        IF last_punch.punch_type IN ["OUT", "BREAK_OUT", "OVERTIME_OUT"] AND punch_type IN ["OUT", "BREAK_OUT", "OVERTIME_OUT"]:
            LOG "Duplicate OUT-type punch detected"
            ALERT_ADMIN "Duplicate OUT-type punch for employee_id: employee.id"
            RETURN NULL

    # Determine punch type and late/early status
    punch_info = CALL determine_punch_type(employee, timestamp)
    punch_type = punch_info.type
    is_late = punch_info.is_late
    lateness_minutes = punch_info.lateness_minutes
    is_early = punch_info.is_early
    earliness_minutes = punch_info.earliness_minutes

    # Validate overtime punches
    IF punch_type IN ["OVERTIME_IN", "OVERTIME_OUT"]:
        approval = EXECUTE SQL "SELECT * FROM OvertimeApproval WHERE employee_id = :employee_id AND date = :date AND is_approved = TRUE" 
                  WITH employee.id, timestamp.date
        IF approval IS NULL:
            LOG "Unapproved overtime punch detected"
            ALERT_ADMIN "Unapproved overtime for employee_id: employee.id"
            RETURN NULL

    # Database Flow: Insert punch record
    new_punch = CREATE RECORD:
        employee_id = employee.id
        punch_type = punch_type
        timestamp = timestamp
        is_late = is_late
        lateness_minutes = lateness_minutes
        is_early = is_early
        earliness_minutes = earliness_minutes
    EXECUTE SQL "INSERT INTO Punch (employee_id, punch_type, timestamp, is_late, lateness_minutes, is_early, earliness_minutes) 
                 VALUES (:employee_id, :punch_type, :timestamp, :is_late, :lateness_minutes, :is_early, :earliness_minutes)" 
                 WITH new_punch
    COMMIT TRANSACTION

    # Check for missing punches at end of day
    IF CALL is_end_of_day(timestamp):
        CALL check_for_missing_punch_out(employee, timestamp)

    RETURN new_punch

FUNCTION determine_punch_type(employee, timestamp):
    punch_time = EXTRACT time FROM timestamp
    shift_start = employee.shift_start_time
    shift_end = employee.shift_end_time

    # Convert times to minutes for comparison
    punch_minutes = punch_time.hours * 60 + punch_time.minutes
    start_minutes = shift_start.hours * 60 + shift_start.minutes
    end_minutes = shift_end.hours * 60 + shift_end.minutes

    # Initialize result
    result = CREATE RECORD:
        type = "UNKNOWN"
        is_late = FALSE
        lateness_minutes = 0
        is_early = FALSE
        earliness_minutes = 0

    # Check for IN or LATE_IN
    IF ABS(punch_minutes - start_minutes) <= time_window:
        result.type = "IN"
    ELSE IF punch_minutes > start_minutes + time_window:
        result.type = "LATE_IN"
        result.is_late = TRUE
        result.lateness_minutes = punch_minutes - start_minutes
    # Check for OUT or EARLY_OUT
    ELSE IF ABS(punch_minutes - end_minutes) <= time_window:
        result.type = "OUT"
    ELSE IF punch_minutes < end_minutes - time_window:
        result.type = "OUT"
        result.is_early = TRUE
        result.earliness_minutes = end_minutes - punch_minutes
    # Check for BREAK_IN or BREAK_OUT (assume breaks occur between shift start and end)
    ELSE IF punch_minutes > start_minutes AND punch_minutes < end_minutes:
        # Determine if BREAK_IN or BREAK_OUT based on last punch
        last_punch = EXECUTE SQL "SELECT * FROM Punch WHERE employee_id = :employee_id AND DATE(timestamp) = :date ORDER BY timestamp DESC LIMIT 1" 
                     WITH employee.id, timestamp.date
        IF last_punch EXISTS AND last_punch.punch_type IN ["IN", "BREAK_IN"]:
            result.type = "BREAK_OUT"
        ELSE:
            result.type = "BREAK_IN"
    # Check for OVERTIME_IN or OVERTIME_OUT
    ELSE IF punch_minutes > end_minutes + time_window:
        last_punch = EXECUTE SQL "SELECT * FROM Punch WHERE employee_id = :employee_id AND DATE(timestamp) = :date ORDER BY timestamp DESC LIMIT 1" 
                     WITH employee.id, timestamp.date
        IF last_punch EXISTS AND last_punch.punch_type IN ["OUT", "BREAK_OUT"]:
            result.type = "OVERTIME_IN"
        ELSE:
            result.type = "OVERTIME_OUT"

    RETURN result

FUNCTION is_end_of_day(timestamp):
    # Check if it's end of day (e.g., 23:59)
    RETURN timestamp.hours = 23 AND timestamp.minutes >= 59

FUNCTION check_for_missing_punch_out(employee, timestamp):
    # Database Flow: Query Punch table for last punch of the day
    last_punch = EXECUTE SQL "SELECT * FROM Punch WHERE employee_id = :employee_id AND DATE(timestamp) = :date ORDER BY timestamp DESC LIMIT 1" 
                 WITH employee.id, timestamp.date

    # If last punch was IN, BREAK_IN, or OVERTIME_IN, mark as defaulter
    IF last_punch EXISTS AND last_punch.punch_type IN ["IN", "BREAK_IN", "OVERTIME_IN"]:
        defaulter_punch = CREATE RECORD:
            employee_id = employee.id
            punch_type = "DEFAULTER"
            timestamp = timestamp
            is_late = FALSE
            lateness_minutes = 0
            is_early = FALSE
            earliness_minutes = 0
        EXECUTE SQL "INSERT INTO Punch (employee_id, punch_type, timestamp, is_late, lateness_minutes, is_early, earliness_minutes) 
                     VALUES (:employee_id, :punch_type, :timestamp, :is_late, :lateness_minutes, :is_early, :earliness_minutes)" 
                     WITH defaulter_punch
        COMMIT TRANSACTION
        LOG "Defaulter punch recorded for employee_id: employee.id"
        ALERT_ADMIN "Missing OUT punch for employee_id: employee.id"

FUNCTION calculate_work_hours(employee_id, date):
    # Database Flow: Query Punch table for all punches on given date
    punches = EXECUTE SQL "SELECT * FROM Punch WHERE employee_id = :employee_id AND DATE(timestamp) = :date ORDER BY timestamp ASC" 
              WITH employee_id, date

    total_work_hours = 0
    total_break_hours = 0
    total_overtime_hours = 0
    last_in_time = NULL
    last_in_type = NULL

    FOR EACH punch IN punches:
        IF punch.punch_type IN ["IN", "BREAK_IN", "OVERTIME_IN"]:
            last_in_time = punch.timestamp
            last_in_type = punch.punch_type
        ELSE IF punch.punch_type IN ["OUT", "BREAK_OUT", "OVERTIME_OUT"] AND last_in_time IS NOT NULL:
            duration = (punch.timestamp - last_in_time) IN hours
            IF last_in_type = "OVERTIME_IN":
                total_overtime_hours = total_overtime_hours + duration
            ELSE:
                total_work_hours = total_work_hours + duration
            last_in_time = NULL
            last_in_type = NULL
        ELSE IF punch.punch_type = "DEFAULTER" AND last_in_time IS NOT NULL:
            employee = EXECUTE SQL "SELECT shift_end_time FROM Employee WHERE id = :employee_id" WITH employee_id
            end_time = COMBINE date WITH employee.shift_end_time
            duration = (end_time - last_in_time) IN hours
            total_work_hours = total_work_hours + duration
            last_in_time = NULL
            last_in_type = NULL

    # Calculate breaks (time between BREAK_OUT and BREAK_IN)
    FOR i FROM 0 TO LENGTH(punches) - 2:
        IF punches[i].punch_type = "BREAK_OUT" AND punches[i+1].punch_type = "BREAK_IN":
            break_duration = (punches[i+1].timestamp - punches[i].timestamp) IN hours
            total_break_hours = total_break_hours + break_duration

    RETURN {
        work_hours: total_work_hours,
        break_hours: total_break_hours,
        overtime_hours: total_overtime_hours
    }