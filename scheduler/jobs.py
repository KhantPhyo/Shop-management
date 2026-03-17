import json
import logging
import sqlite3
import urllib.request
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


def get_db():
    db = sqlite3.connect(Config.DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db


def check_and_send_reminders():
    """Check for tasks needing reminders and send them"""
    logger.info("Running reminder check...")
    db = get_db()
    try:
        reminder_interval = Config.REMINDER_INTERVAL_MINUTES

        # Pending tasks older than 1 hour that haven't been reminded recently
        pending_tasks = db.execute(
            """SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id
               WHERE t.status = 'pending'
               AND t.created_at < datetime('now', '-1 hour')
               AND (t.last_reminder_at IS NULL OR t.last_reminder_at < datetime('now', ? || ' minutes'))""",
            (f'-{reminder_interval}',)
        ).fetchall()

        # Tasks approaching deadline (within 2 hours)
        deadline_tasks = db.execute(
            """SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id
               WHERE t.status IN ('accepted', 'in_progress')
               AND t.deadline IS NOT NULL
               AND t.deadline < datetime('now', '+2 hours')
               AND t.deadline > datetime('now')"""
        ).fetchall()

        import asyncio
        from tg_bots.shop_bot_manager import shop_bot_manager

        loop = asyncio.new_event_loop()

        for task in pending_tasks:
            try:
                loop.run_until_complete(shop_bot_manager.send_reminder(task['shop_id'], dict(task)))
                db.execute(
                    "UPDATE tasks SET reminder_count = reminder_count + 1, last_reminder_at = datetime('now') WHERE id = ?",
                    (task['id'],)
                )
                db.execute(
                    "INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'reminded', 'system')",
                    (task['id'],)
                )
            except Exception as e:
                logger.error(f"Failed to send reminder for task {task['task_id']}: {e}")

        for task in deadline_tasks:
            try:
                loop.run_until_complete(shop_bot_manager.send_reminder(task['shop_id'], dict(task)))
            except Exception as e:
                logger.error(f"Failed to send deadline reminder for task {task['task_id']}: {e}")

        db.commit()
        loop.close()
        logger.info(f"Sent {len(pending_tasks)} pending reminders and {len(deadline_tasks)} deadline reminders")
    except Exception as e:
        logger.error(f"Error in reminder check: {e}")
    finally:
        db.close()


def check_overdue_tasks():
    """Check and mark overdue tasks"""
    logger.info("Running overdue check...")
    db = get_db()
    try:
        overdue_tasks = db.execute(
            """SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id
               WHERE t.deadline < datetime('now')
               AND t.status NOT IN ('done', 'overdue')"""
        ).fetchall()

        import asyncio
        from tg_bots.shop_bot_manager import shop_bot_manager

        loop = asyncio.new_event_loop()

        for task in overdue_tasks:
            try:
                db.execute(
                    "UPDATE tasks SET status = 'overdue', updated_at = datetime('now') WHERE id = ?",
                    (task['id'],)
                )
                db.execute(
                    "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'overdue', 'system', 'Deadline passed')",
                    (task['id'],)
                )

                loop.run_until_complete(shop_bot_manager.send_message(
                    task['shop_id'],
                    f"*OVERDUE!*\n\nTask `{task['task_id']}` - {task['title']}\nDeadline ကျော်သွားပြီ!\n\nအမြန်ဆုံးပြီးအောင်လုပ်ပါ!"
                ))
            except Exception as e:
                logger.error(f"Error processing overdue task {task['task_id']}: {e}")

        db.commit()
        loop.close()
        logger.info(f"Marked {len(overdue_tasks)} tasks as overdue")
    except Exception as e:
        logger.error(f"Error in overdue check: {e}")
    finally:
        db.close()


def generate_scheduled_tasks():
    """Generate new task instances from recurring task templates"""
    logger.info("Running scheduled task generation...")
    db = get_db()
    try:
        registries = db.execute(
            """SELECT r.*, t.shop_id, t.title, t.description, t.priority, t.fine_amount_mmk,
                      t.schedule_type, t.schedule_day, t.schedule_time
               FROM scheduled_tasks_registry r
               JOIN tasks t ON r.task_template_id = t.id
               WHERE r.is_active = 1"""
        ).fetchall()

        from task_utils import generate_task_id
        import asyncio
        from tg_bots.shop_bot_manager import shop_bot_manager

        today = datetime.now()
        loop = asyncio.new_event_loop()

        for reg in registries:
            should_create = False
            schedule_type = reg['schedule_type']

            if schedule_type == 'daily':
                should_create = True
            elif schedule_type == 'weekly' and reg['schedule_day'] is not None:
                should_create = today.weekday() == reg['schedule_day']
            elif schedule_type == 'monthly' and reg['schedule_day'] is not None:
                should_create = today.day == reg['schedule_day']

            if should_create:
                try:
                    task_id = generate_task_id(db)
                    deadline_str = None
                    if reg['schedule_time']:
                        deadline_str = f"{today.strftime('%Y-%m-%d')} {reg['schedule_time']}:00"

                    db.execute(
                        """INSERT INTO tasks (task_id, shop_id, title, description, priority, deadline,
                           fine_amount_mmk, schedule_type, created_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'one_time', 'system')""",
                        (task_id, reg['shop_id'], reg['title'], reg['description'],
                         reg['priority'], deadline_str, reg['fine_amount_mmk'])
                    )
                    new_task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                    db.execute(
                        "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'created', 'system', 'Auto-generated from scheduled task')",
                        (new_task_id,)
                    )

                    db.execute(
                        "UPDATE scheduled_tasks_registry SET last_generated_at = datetime('now') WHERE id = ?",
                        (reg['id'],)
                    )

                    task_data = {
                        'task_id': task_id, 'title': reg['title'], 'description': reg['description'],
                        'priority': reg['priority'], 'deadline': deadline_str, 'fine_amount_mmk': reg['fine_amount_mmk']
                    }
                    loop.run_until_complete(shop_bot_manager.send_task_notification(reg['shop_id'], task_data))

                    logger.info(f"Generated scheduled task: {task_id}")
                except Exception as e:
                    logger.error(f"Error generating scheduled task: {e}")

        db.commit()
        loop.close()
    except Exception as e:
        logger.error(f"Error in scheduled task generation: {e}")
    finally:
        db.close()


def check_announcement_reminders():
    """Remind shops that haven't responded to announcements within 2 hours"""
    logger.info("Running announcement reminder check...")
    db = get_db()
    try:
        # Find announcements created within last 24 hours that have unresponded shops
        announcements = db.execute(
            """SELECT * FROM announcements
               WHERE created_at > datetime('now', '-24 hours')
               AND created_at < datetime('now', '-2 hours')"""
        ).fetchall()

        sent = 0
        for ann in announcements:
            if ann['target_type'] == 'all':
                shops = db.execute("SELECT * FROM shops WHERE is_active = 1").fetchall()
            else:
                shops = db.execute(
                    "SELECT * FROM shops WHERE id = ? AND is_active = 1",
                    (ann['target_shop_id'],)
                ).fetchall()

            for shop in shops:
                # Check if already responded
                responded = db.execute(
                    "SELECT id FROM announcement_responses WHERE announcement_id = ? AND shop_id = ?",
                    (ann['id'], shop['id'])
                ).fetchone()

                if not responded:
                    try:
                        keyboard = {
                            "inline_keyboard": [[
                                {"text": "✅ Agree", "callback_data": f"ann_agree_{ann['id']}"},
                                {"text": "👁 Acknowledge", "callback_data": f"ann_ack_{ann['id']}"},
                                {"text": "❌ Disagree", "callback_data": f"ann_disagree_{ann['id']}"}
                            ]]
                        }

                        msg = (
                            f"⏰ *REMINDER - Announcement*\n\n"
                            f"{ann['message']}\n\n"
                            f"⚠️ မဖြေရသေးပါ။ အောက်က ခလုတ်တစ်ခုကို နှိပ်ပေးပါ။"
                        )

                        payload = json.dumps({
                            'chat_id': shop['telegram_chat_id'],
                            'text': msg,
                            'parse_mode': 'Markdown',
                            'reply_markup': keyboard
                        }).encode('utf-8')

                        req = urllib.request.Request(
                            f"https://api.telegram.org/bot{shop['telegram_bot_token']}/sendMessage",
                            data=payload,
                            headers={'Content-Type': 'application/json'}
                        )
                        urllib.request.urlopen(req, timeout=10)
                        sent += 1
                    except Exception as e:
                        logger.warning(f"Failed to send announcement reminder to {shop['shop_name']}: {e}")

        logger.info(f"Sent {sent} announcement reminders")
    except Exception as e:
        logger.error(f"Error in announcement reminder check: {e}")
    finally:
        db.close()
