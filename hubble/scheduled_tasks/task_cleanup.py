from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from retry_tasks_lib.scheduled.cleanup import delete_old_task_data

from hubble.config import settings
from hubble.db.session import SessionMaker
from hubble.scheduled_tasks.scheduler import acquire_lock, cron_scheduler


@acquire_lock(runner=cron_scheduler)
def cleanup_old_tasks() -> None:
    # today at midnight - 6 * 30 days (circa 6 months ago)
    tz_info = ZoneInfo(cron_scheduler.tz)
    time_reference = datetime.now(tz=tz_info).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=settings.TASK_DATA_RETENTION_DAYS
    )
    with SessionMaker() as db_session:
        delete_old_task_data(db_session=db_session, time_reference=time_reference)
