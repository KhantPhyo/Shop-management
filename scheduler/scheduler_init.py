from apscheduler.schedulers.background import BackgroundScheduler
from scheduler.jobs import check_and_send_reminders, check_overdue_tasks, generate_scheduled_tasks, check_announcement_reminders

scheduler = BackgroundScheduler()


def init_scheduler():
    """Initialize and start the scheduler with all jobs"""
    scheduler.add_job(check_and_send_reminders, 'interval', minutes=30, id='reminder_check', replace_existing=True)
    scheduler.add_job(check_overdue_tasks, 'interval', minutes=15, id='overdue_check', replace_existing=True)
    scheduler.add_job(generate_scheduled_tasks, 'cron', hour=0, minute=0, id='scheduled_task_gen', replace_existing=True)
    scheduler.add_job(check_announcement_reminders, 'interval', minutes=30, id='announcement_reminder', replace_existing=True)
    scheduler.start()
