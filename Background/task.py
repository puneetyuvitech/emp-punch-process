from datetime import datetime
from fastapi import BackgroundTasks, FastAPI
import logging
from main import process_punch, check_for_missing_punch_out
from utils.helper import mock_employees
app = FastAPI()
@app.post("/punch")
def receive_punch(badge_id: str, timestamp: datetime, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_punch, badge_id, timestamp)
    return {"status": "Punch received, processing in background."}

def run_end_of_day_check():
    now = datetime.now()
    logging.info("Running end-of-day defaulter check for all employees")
    for emp in mock_employees:
        if emp["is_active"]:
            check_for_missing_punch_out(emp, now)
    logging.info("End-of-day defaulter check completed.")