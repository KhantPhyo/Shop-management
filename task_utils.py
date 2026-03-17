from datetime import datetime


def generate_task_id(db):
    """Generate task ID in format TASK-YYYYMMDD-XXXX"""
    today = datetime.now().strftime('%Y%m%d')
    prefix = f'TASK-{today}-'
    cursor = db.execute(
        "SELECT MAX(CAST(SUBSTR(task_id, -4) AS INTEGER)) FROM tasks WHERE task_id LIKE ?",
        (f'TASK-{today}-%',)
    )
    result = cursor.fetchone()[0]
    next_num = (result or 0) + 1
    return f'{prefix}{next_num:04d}'


def format_task_message(task):
    """Format task data for Telegram messages"""
    priority_emoji = {'low': '\U0001f7e2', 'medium': '\U0001f535', 'high': '\U0001f7e0', 'urgent': '\U0001f534'}.get(task['priority'], '\u26aa')
    status_emoji = {
        'pending': '\u23f3', 'accepted': '\u2705', 'rejected': '\u274c',
        'in_progress': '\U0001f504', 'done': '\u2705', 'overdue': '\u26a0\ufe0f'
    }.get(task['status'], '\u2753')

    return (
        f"Task ID: `{task['task_id']}`\n"
        f"Title: {task['title']}\n"
        f"Description: {task.get('description', '-')}\n"
        f"Priority: {priority_emoji} {task['priority']}\n"
        f"Status: {status_emoji} {task['status']}\n"
        f"Deadline: {task.get('deadline', 'N/A')}\n"
        f"Fine: {task.get('fine_amount_mmk', 0)} MMK"
    )


def calculate_time_remaining(deadline_str):
    """Calculate time remaining until deadline"""
    if not deadline_str:
        return 'N/A'
    try:
        deadline = datetime.fromisoformat(deadline_str)
        now = datetime.now()
        diff = deadline - now
        if diff.total_seconds() < 0:
            hours = abs(diff.total_seconds()) / 3600
            if hours < 1:
                return f"overdue by {int(abs(diff.total_seconds()) / 60)} mins"
            return f"overdue by {hours:.1f} hrs"
        hours = diff.total_seconds() / 3600
        if hours < 1:
            return f"in {int(diff.total_seconds() / 60)} mins"
        if hours < 24:
            return f"in {hours:.1f} hrs"
        return f"in {int(diff.days)} days"
    except (ValueError, TypeError):
        return 'N/A'
