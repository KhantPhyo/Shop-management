import json
import urllib.request
import urllib.error
import logging
from flask import Blueprint, request, jsonify
from database import get_db
from auth_utils import token_required
from task_utils import generate_task_id

logger = logging.getLogger(__name__)


def send_telegram_notification_direct(token, chat_id, task_data):
    """Send task notification directly via Telegram API (fallback when bot not registered)"""
    priority_emoji = {'low': '🟢', 'medium': '🔵', 'high': '🟠', 'urgent': '🔴'}.get(
        task_data.get('priority', 'medium'), '⚪')

    report_types = task_data.get('required_report_type', 'photo') or 'photo'
    type_labels = {'photo': '📸 Photo', 'excel': '📊 Excel', 'file': '📄 File', 'text': '💬 Text'}
    report_display = ', '.join(type_labels.get(t.strip(), t.strip()) for t in report_types.split(','))

    message = (
        f"📋 *TASK အသစ်ရောက်ပါပြီ*\n\n"
        f"Task ID: `{task_data['task_id']}`\n"
        f"ခေါင်းစဥ်: {task_data['title']}\n"
        f"အကြောင်းအရာ: {task_data.get('description', '-')}\n"
        f"Priority: {priority_emoji} {task_data.get('priority', 'medium')}\n"
        f"Deadline: {task_data.get('deadline', 'N/A')}\n"
        f"ဒဏ်ကြေး (ကျော်ရင်): {task_data.get('fine_amount_mmk', 0)} MMK\n"
        f"Report: {report_display}\n\n"
        f"၁ နာရီအတွင်း လက်ခံပါ။"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ လက်ခံမယ်", "callback_data": f"accept_{task_data['task_id']}"},
            {"text": "❌ ငြင်းမယ်", "callback_data": f"reject_{task_data['task_id']}"}
        ]]
    }

    payload = json.dumps({
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown',
        'reply_markup': keyboard
    }).encode('utf-8')

    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode('utf-8'))

task_bp = Blueprint('tasks', __name__)


@task_bp.route('/api/tasks', methods=['GET'])
@token_required
def get_tasks(current_user):
    db = get_db()
    try:
        sql = """SELECT t.*, s.shop_name, s.leader_name
                 FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE 1=1"""
        params = []

        status = request.args.get('status')
        if status and status != 'all':
            sql += " AND t.status = ?"
            params.append(status)

        shop_id = request.args.get('shop_id')
        if shop_id:
            sql += " AND t.shop_id = ?"
            params.append(int(shop_id))

        priority = request.args.get('priority')
        if priority and priority != 'all':
            sql += " AND t.priority = ?"
            params.append(priority)

        date_from = request.args.get('date_from')
        if date_from:
            sql += " AND date(t.created_at) >= ?"
            params.append(date_from)

        date_to = request.args.get('date_to')
        if date_to:
            sql += " AND date(t.created_at) <= ?"
            params.append(date_to)

        search = request.args.get('search')
        if search:
            sql += " AND (t.task_id LIKE ? OR t.title LIKE ?)"
            params.extend([f'%{search}%', f'%{search}%'])

        sql += " ORDER BY t.created_at DESC"

        tasks = db.execute(sql, params).fetchall()
        return jsonify([dict(t) for t in tasks])
    finally:
        db.close()


@task_bp.route('/api/tasks/<int:task_id>', methods=['GET'])
@token_required
def get_task(task_id, current_user):
    db = get_db()
    try:
        task = db.execute(
            """SELECT t.*, s.shop_name, s.leader_name
               FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE t.id = ?""",
            (task_id,)
        ).fetchone()

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        task_dict = dict(task)

        reports = db.execute(
            "SELECT * FROM task_reports WHERE task_id = ? ORDER BY submitted_at", (task_id,)
        ).fetchall()
        task_dict['reports'] = [dict(r) for r in reports]

        logs = db.execute(
            "SELECT * FROM task_logs WHERE task_id = ? ORDER BY created_at", (task_id,)
        ).fetchall()
        task_dict['logs'] = [dict(l) for l in logs]

        return jsonify(task_dict)
    finally:
        db.close()


@task_bp.route('/api/tasks', methods=['POST'])
@token_required
def create_task(current_user):
    data = request.get_json()
    if not data or not data.get('shop_id') or not data.get('title'):
        return jsonify({'error': 'shop_id and title are required'}), 400

    db = get_db()
    try:
        # Verify shop exists
        shop = db.execute("SELECT * FROM shops WHERE id = ? AND is_active = 1", (data['shop_id'],)).fetchone()
        if not shop:
            return jsonify({'error': 'Shop not found or inactive'}), 404

        task_id = generate_task_id(db)

        db.execute(
            """INSERT INTO tasks (task_id, shop_id, title, description, priority, deadline,
               fine_amount_mmk, schedule_type, schedule_day, schedule_time, required_report_type, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'web')""",
            (task_id, data['shop_id'], data['title'], data.get('description', ''),
             data.get('priority', 'medium'), data.get('deadline'),
             data.get('fine_amount_mmk', 0), data.get('schedule_type', 'one_time'),
             data.get('schedule_day'), data.get('schedule_time'),
             data.get('required_report_type', 'photo'))
        )
        db.commit()

        new_task_db_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Log creation
        db.execute(
            "INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'created', 'admin')",
            (new_task_db_id,)
        )

        # If recurring, register in scheduled_tasks_registry
        schedule_type = data.get('schedule_type', 'one_time')
        if schedule_type != 'one_time':
            cron_expr = ''
            if schedule_type == 'daily':
                cron_expr = '0 0 * * *'
            elif schedule_type == 'weekly':
                cron_expr = f"0 0 * * {data.get('schedule_day', 0)}"
            elif schedule_type == 'monthly':
                cron_expr = f"0 0 {data.get('schedule_day', 1)} * *"

            db.execute(
                """INSERT INTO scheduled_tasks_registry (task_template_id, cron_expression, is_active)
                   VALUES (?, ?, 1)""",
                (new_task_db_id, cron_expr)
            )

        db.commit()

        task = db.execute(
            "SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE t.id = ?",
            (new_task_db_id,)
        ).fetchone()
        task_dict = dict(task)

        # Send Telegram notification directly using shop's token/chat_id
        try:
            send_telegram_notification_direct(shop['telegram_bot_token'], shop['telegram_chat_id'], task_dict)
            logger.info(f"Telegram notification sent for task {task_id} to shop {data['shop_id']}")
        except Exception as e:
            logger.warning(f"Failed to send Telegram notification for task {task_id}: {e}")

        return jsonify(task_dict), 201
    finally:
        db.close()


@task_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
@token_required
def update_task(task_id, current_user):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    db = get_db()
    try:
        task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        allowed_fields = ['title', 'description', 'priority', 'status', 'deadline',
                          'fine_amount_mmk', 'shop_id', 'schedule_type', 'schedule_day', 'schedule_time',
                          'required_report_type']
        updates = []
        values = []
        changes = {}

        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = ?")
                values.append(data[field])
                changes[field] = {'old': task[field], 'new': data[field]}

        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400

        updates.append("updated_at = datetime('now')")
        values.append(task_id)

        db.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
        db.execute(
            "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'edited', 'admin', ?)",
            (task_id, json.dumps(changes))
        )
        db.commit()

        updated = db.execute(
            "SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE t.id = ?",
            (task_id,)
        ).fetchone()

        # Notify shop about update
        try:
            shop_info = db.execute("SELECT telegram_bot_token, telegram_chat_id FROM shops WHERE id = ?",
                                   (updated['shop_id'],)).fetchone()
            if shop_info:
                msg = f"✏️ *TASK ပြင်ဆင်ပြီး*\n\nTask ID: `{updated['task_id']}`\nပြောင်းလဲချက်: {', '.join(changes.keys())}"
                payload = json.dumps({'chat_id': shop_info['telegram_chat_id'], 'text': msg, 'parse_mode': 'Markdown'}).encode('utf-8')
                req = urllib.request.Request(f"https://api.telegram.org/bot{shop_info['telegram_bot_token']}/sendMessage",
                                            data=payload, headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.warning(f"Failed to notify shop about task update: {e}")

        return jsonify(dict(updated))
    finally:
        db.close()


@task_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@token_required
def delete_task(task_id, current_user):
    db = get_db()
    try:
        task = db.execute(
            "SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE t.id = ?",
            (task_id,)
        ).fetchone()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        db.execute(
            "INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'deleted', 'admin')",
            (task_id,)
        )
        db.execute("DELETE FROM task_reports WHERE task_id = ?", (task_id,))
        db.execute("DELETE FROM task_logs WHERE task_id = ?", (task_id,))
        db.execute("DELETE FROM scheduled_tasks_registry WHERE task_template_id = ?", (task_id,))
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()

        # Notify shop
        try:
            shop_info = db.execute("SELECT telegram_bot_token, telegram_chat_id FROM shops WHERE id = ?",
                                   (task['shop_id'],)).fetchone()
            if shop_info:
                msg = f"🗑️ *TASK ဖျက်ပြီး*\n\nTask ID: `{task['task_id']}`\nခေါင်းစဥ်: {task['title']}\n\nAdmin က ဖျက်လိုက်ပါပြီ။"
                payload = json.dumps({'chat_id': shop_info['telegram_chat_id'], 'text': msg, 'parse_mode': 'Markdown'}).encode('utf-8')
                req = urllib.request.Request(f"https://api.telegram.org/bot{shop_info['telegram_bot_token']}/sendMessage",
                                            data=payload, headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.warning(f"Failed to notify shop about task deletion: {e}")

        return jsonify({'message': 'Task deleted successfully'})
    finally:
        db.close()


@task_bp.route('/api/tasks/<int:task_id>/fine', methods=['POST'])
@token_required
def apply_fine(task_id, current_user):
    data = request.get_json()
    if not data or 'amount_mmk' not in data:
        return jsonify({'error': 'amount_mmk is required'}), 400

    amount = data['amount_mmk']
    db = get_db()
    try:
        task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        db.execute(
            "UPDATE tasks SET fine_amount_mmk = ?, updated_at = datetime('now') WHERE id = ?",
            (amount, task_id)
        )
        db.execute(
            "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'fined', 'admin', ?)",
            (task_id, json.dumps({'amount': amount}))
        )
        db.commit()

        # Notify shop about fine
        try:
            shop_info = db.execute("SELECT telegram_bot_token, telegram_chat_id FROM shops WHERE id = ?",
                                   (task['shop_id'],)).fetchone()
            if shop_info:
                msg = (f"💸 *ဒဏ်ကြေးတပ်ပြီး*\n\nTask ID: `{task['task_id']}`\n"
                       f"ခေါင်းစဥ်: {task['title']}\nဒဏ်ကြေး: {amount} MMK\n"
                       f"အကြောင်းပြချက်: Deadline ကျော်\n\nအမြန်ဆုံးပြီးအောင်လုပ်ပါ။")
                payload = json.dumps({'chat_id': shop_info['telegram_chat_id'], 'text': msg, 'parse_mode': 'Markdown'}).encode('utf-8')
                req = urllib.request.Request(f"https://api.telegram.org/bot{shop_info['telegram_bot_token']}/sendMessage",
                                            data=payload, headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.warning(f"Failed to notify shop about fine: {e}")

        return jsonify({'message': f'Fine of {amount} MMK applied', 'fine_amount_mmk': amount})
    finally:
        db.close()


@task_bp.route('/api/tasks/<int:task_id>/reports', methods=['GET'])
@token_required
def get_task_reports(task_id, current_user):
    db = get_db()
    try:
        reports = db.execute(
            "SELECT * FROM task_reports WHERE task_id = ? ORDER BY submitted_at", (task_id,)
        ).fetchall()
        return jsonify([dict(r) for r in reports])
    finally:
        db.close()


@task_bp.route('/api/tasks/<int:task_id>/reassign', methods=['POST'])
@token_required
def reassign_task(task_id, current_user):
    data = request.get_json()
    if not data or not data.get('new_shop_id'):
        return jsonify({'error': 'new_shop_id is required'}), 400

    new_shop_id = data['new_shop_id']
    db = get_db()
    try:
        task = db.execute(
            "SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE t.id = ?",
            (task_id,)
        ).fetchone()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        new_shop = db.execute("SELECT * FROM shops WHERE id = ? AND is_active = 1", (new_shop_id,)).fetchone()
        if not new_shop:
            return jsonify({'error': 'Target shop not found or inactive'}), 404

        old_shop_id = task['shop_id']
        old_shop_name = task['shop_name']

        # Reset task status for new owner
        db.execute(
            """UPDATE tasks SET shop_id = ?, status = 'pending', accepted_at = NULL,
               started_at = NULL, completed_at = NULL, rejection_reason = NULL,
               updated_at = datetime('now') WHERE id = ?""",
            (new_shop_id, task_id)
        )
        db.execute(
            "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'reassigned', 'admin', ?)",
            (task_id, json.dumps({'from_shop': old_shop_name, 'to_shop': new_shop['shop_name']}))
        )
        db.commit()

        updated = db.execute(
            "SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE t.id = ?",
            (task_id,)
        ).fetchone()

        # Notify both shops
        try:
            # Notify old shop
            old_shop_info = db.execute("SELECT telegram_bot_token, telegram_chat_id FROM shops WHERE id = ?",
                                       (old_shop_id,)).fetchone()
            if old_shop_info:
                msg = f"*TASK ပြောင်းရွှေ့ပြီး*\n\nTask `{task['task_id']}` - {task['title']}\n{new_shop['shop_name']} ဆီ ပြောင်းလိုက်ပါပြီ။"
                payload = json.dumps({'chat_id': old_shop_info['telegram_chat_id'], 'text': msg, 'parse_mode': 'Markdown'}).encode('utf-8')
                req = urllib.request.Request(f"https://api.telegram.org/bot{old_shop_info['telegram_bot_token']}/sendMessage",
                                            data=payload, headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.warning(f"Failed to notify old shop about reassignment: {e}")

        try:
            # Notify new shop with full task notification
            send_telegram_notification_direct(new_shop['telegram_bot_token'], new_shop['telegram_chat_id'], dict(updated))
        except Exception as e:
            logger.warning(f"Failed to notify new shop about reassignment: {e}")

        return jsonify(dict(updated))
    finally:
        db.close()
