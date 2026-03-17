import json
import urllib.request
import urllib.error
from flask import Blueprint, request, jsonify
from database import get_db
from auth_utils import token_required


def telegram_api_get(url, timeout=10):
    """Make a GET request to Telegram API using urllib"""
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode('utf-8'))


def telegram_api_post(url, data, timeout=10):
    """Make a POST request to Telegram API using urllib"""
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode('utf-8'))

shop_bp = Blueprint('shops', __name__)


@shop_bp.route('/api/shops', methods=['GET'])
@token_required
def get_shops(current_user):
    db = get_db()
    try:
        shops = db.execute(
            """SELECT s.*,
               (SELECT COUNT(*) FROM tasks t WHERE t.shop_id = s.id AND t.status NOT IN ('done')) as active_tasks
               FROM shops s WHERE s.is_active = 1 ORDER BY s.created_at DESC"""
        ).fetchall()
        return jsonify([dict(s) for s in shops])
    finally:
        db.close()


@shop_bp.route('/api/shops', methods=['POST'])
@token_required
def create_shop(current_user):
    data = request.get_json()
    required = ['shop_name', 'leader_name', 'phone_number', 'telegram_bot_token', 'telegram_chat_id']
    if not data or not all(data.get(f) for f in required):
        return jsonify({'error': 'All fields are required'}), 400

    db = get_db()
    try:
        db.execute(
            """INSERT INTO shops (shop_name, leader_name, phone_number, telegram_bot_token, telegram_chat_id)
               VALUES (?, ?, ?, ?, ?)""",
            (data['shop_name'], data['leader_name'], data['phone_number'],
             data['telegram_bot_token'], data['telegram_chat_id'])
        )
        db.commit()
        shop_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        shop = db.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()

        # Register bot with shop_bot_manager so it can receive callbacks
        try:
            import asyncio
            from tg_bots.shop_bot_manager import shop_bot_manager
            if shop_bot_manager.loop:
                future = asyncio.run_coroutine_threadsafe(
                    shop_bot_manager.register_shop_bot(shop_id, data['telegram_bot_token'], data['telegram_chat_id']),
                    shop_bot_manager.loop
                )
                future.result(timeout=10)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not register bot for new shop: {e}")

        return jsonify(dict(shop)), 201
    finally:
        db.close()


@shop_bp.route('/api/shops/<int:shop_id>', methods=['PUT'])
@token_required
def update_shop(shop_id, current_user):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    db = get_db()
    try:
        shop = db.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
        if not shop:
            return jsonify({'error': 'Shop not found'}), 404

        allowed_fields = ['shop_name', 'leader_name', 'phone_number', 'telegram_bot_token', 'telegram_chat_id', 'is_active']
        updates = []
        values = []
        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = ?")
                values.append(data[field])

        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400

        updates.append("updated_at = datetime('now')")
        values.append(shop_id)

        db.execute(f"UPDATE shops SET {', '.join(updates)} WHERE id = ?", values)
        db.commit()

        updated = db.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
        return jsonify(dict(updated))
    finally:
        db.close()


@shop_bp.route('/api/shops/<int:shop_id>', methods=['DELETE'])
@token_required
def delete_shop(shop_id, current_user):
    db = get_db()
    try:
        shop = db.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
        if not shop:
            return jsonify({'error': 'Shop not found'}), 404

        db.execute("UPDATE shops SET is_active = 0, updated_at = datetime('now') WHERE id = ?", (shop_id,))
        db.commit()
        return jsonify({'message': 'Shop deactivated successfully'})
    finally:
        db.close()


@shop_bp.route('/api/shops/get-chat-id', methods=['POST'])
@token_required
def get_bot_chat_id(current_user):
    """Send a message via the bot asking for chat ID, and fetch recent updates to find chat IDs"""
    data = request.get_json()
    token = data.get('telegram_bot_token', '').strip() if data else ''
    if not token:
        return jsonify({'error': 'telegram_bot_token is required'}), 400

    try:
        # Get bot info first to verify token
        try:
            bot_data = telegram_api_get(f'https://api.telegram.org/bot{token}/getMe')
        except urllib.error.HTTPError:
            return jsonify({'error': 'Invalid bot token'}), 400

        if not bot_data.get('ok'):
            return jsonify({'error': 'Invalid bot token'}), 400

        bot_name = bot_data['result'].get('username', 'the bot')

        # Get recent updates to find chat IDs
        chat_ids = []
        try:
            updates_data = telegram_api_get(f'https://api.telegram.org/bot{token}/getUpdates')
            if updates_data.get('ok'):
                for update in updates_data.get('result', []):
                    msg = update.get('message', {})
                    chat = msg.get('chat', {})
                    if chat.get('id'):
                        chat_info = {
                            'chat_id': str(chat['id']),
                            'name': chat.get('first_name', '') + (' ' + chat.get('last_name', '') if chat.get('last_name') else ''),
                            'username': chat.get('username', ''),
                            'type': chat.get('type', '')
                        }
                        # Deduplicate
                        if not any(c['chat_id'] == chat_info['chat_id'] for c in chat_ids):
                            chat_ids.append(chat_info)
        except Exception:
            pass  # Updates fetch failed, still return bot info

        if chat_ids:
            return jsonify({
                'success': True,
                'bot_name': bot_name,
                'chat_ids': chat_ids,
                'message': f'Found {len(chat_ids)} chat(s). Select the correct Chat ID.'
            })
        else:
            return jsonify({
                'success': True,
                'bot_name': bot_name,
                'chat_ids': [],
                'message': f'No chats found. Please send /start to @{bot_name} on Telegram first, then try again.'
            })
    except TimeoutError:
        return jsonify({'error': 'Telegram API timeout. Try again.'}), 504
    except Exception as e:
        return jsonify({'error': f'Failed to connect: {str(e)}'}), 500


@shop_bp.route('/api/shops/test-bot', methods=['POST'])
@token_required
def test_bot_connection(current_user):
    """Test that the bot can send a message to the given chat ID (activate/verify binding)"""
    data = request.get_json()
    token = data.get('telegram_bot_token', '').strip() if data else ''
    chat_id = data.get('telegram_chat_id', '').strip() if data else ''
    if not token or not chat_id:
        return jsonify({'error': 'telegram_bot_token and telegram_chat_id are required'}), 400

    try:
        result = telegram_api_post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            {
                'chat_id': chat_id,
                'text': '✅ Telegram Bot ချိတ်ဆက်မှု အောင်မြင်ပါသည်!\n\nThis bot is now connected to the Shop Task Management System.',
                'parse_mode': 'Markdown'
            }
        )
        if result.get('ok'):
            return jsonify({'success': True, 'message': 'Connection successful! Test message sent.'})
        else:
            error_desc = result.get('description', 'Unknown error')
            return jsonify({'success': False, 'error': f'Telegram error: {error_desc}'}), 400
    except urllib.error.HTTPError as e:
        try:
            error_body = json.loads(e.read().decode('utf-8'))
            error_desc = error_body.get('description', 'Unknown error')
        except Exception:
            error_desc = str(e)
        return jsonify({'success': False, 'error': f'Telegram error: {error_desc}'}), 400
    except TimeoutError:
        return jsonify({'error': 'Telegram API timeout. Try again.'}), 504
    except Exception as e:
        return jsonify({'error': f'Failed to send test message: {str(e)}'}), 500
