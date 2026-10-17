"""Local isolated calendar/trend QA; all records are labelled examples."""
from pathlib import Path
import ui_piano_test_server as qa
from seed_followup_showcase import seed_showcase
from sqlalchemy import select
from app.db.models import StaffUser

with qa.maker() as db:
    user=db.scalar(select(StaffUser).where(StaffUser.username=='browserqa'))
    user.id='followup-browser-qa-staff'
    db.commit()
    owner=user.id
    output=Path(__file__).resolve().parents[1]/'_deploy'/'followup-qa'
    seed_showcase(db,[owner],output_root=output)

if __name__=='__main__':
    import uvicorn
    uvicorn.run(qa.app,host='127.0.0.1',port=8013,log_level='warning')
