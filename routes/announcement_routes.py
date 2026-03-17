import json
import logging
import urllib.request
from flask import Blueprint, request, jsonify
from database import get_db
from auth_utils import token_required

logger = logging.getLogger(__name__)

announcement_bp = Blueprint('announcements', __name__)


@announcement_bp.route('/api/announcements', methods=['GET'])
@token_required
def get_announcements(current_user):
    db = get_db()
    try:
        announcements = db.execute(
            """SELECT a.*, s.shop_name as target_shop_name
               FROM announcements a
               LEFT JOIN shops s ON a.target_shop_id = s.id
               ORDER BY a.created_at DESC"""
        ).fetchall()

        result = []
        for ann in announcements:
            ann_dict = dict(ann)
            # Get responses
            responses = db.execute(
                """SELECT ar.*, s.shop_name
                   FROM announcement_responses ar
                   JOIN shops s ON ar.shop_id = s.id
                   WHERE ar.announcement_id = ?
                   ORDER BY ar.responded_at""",
                (ann['id'],)
            ).fetchall()
            ann_dict['responses'] = [dict(r) for r in responses]

            # Get target shops count
            if ann['target_type'] == 'all':
                total = db.execute("SELECT COUNT(*) FROM shops WHERE is_active = 1").fetchone()[0]
            else:
                total = 1
            ann_dict['total_targets'] = total

            # Count by response type
            ann_dict['agree_count'] = sum(1 for r in responses if r['response'] == 'agree')
            ann_dict['acknowledge_count'] = sum(1 for r in responses if r['response'] == 'acknowledge')
            ann_dict['disagree_count'] = sum(1 for r in responses if r['response'] == 'disagree')
            ann_dict['responded_count'] = len(responses)

            result.append(ann_dict)

        return jsonify(result)
    finally:
        db.close()


@announcement_bp.route('/api/announcements', methods=['POST'])
@token_required
def create_announcement(current_user):
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({'error': 'message is required'}), 400

    target_type = data.get('target_type', 'all')  # 'all' or 'single'
    target_shop_id = data.get('target_shop_id') if target_type == 'single' else None

    db = get_db()
    try:
        db.execute(
            "INSERT INTO announcements (message, target_type, target_shop_id) VALUES (?, ?, ?)",
            (data['message'], target_type, target_shop_id)
        )
        db.commit()
        ann_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Determine target shops
        if target_type == 'all':
            shops = db.execute("SELECT * FROM shops WHERE is_active = 1").fetchall()
        else:
            shops = db.execute("SELECT * FROM shops WHERE id = ? AND is_active = 1", (target_shop_id,)).fetchall()

        # Send to each shop via Telegram
        sent_count = 0
        for shop in shops:
            try:
                keyboard = {
                    "inline_keyboard": [[
                        {"text": "✅ Agree", "callback_data": f"ann_agree_{ann_id}"},
                        {"text": "👁 Acknowledge", "callback_data": f"ann_ack_{ann_id}"},
                        {"text": "❌ Disagree", "callback_data": f"ann_disagree_{ann_id}"}
                    ]]
                }

                msg = (
                    f"📢 *ANNOUNCEMENT*\n\n"
                    f"{data['message']}\n\n"
                    f"အောက်က ခလုတ်တစ်ခုကို နှိပ်ပေးပါ။"
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
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send announcement to shop {shop['shop_name']}: {e}")

        ann = db.execute(
            """SELECT a.*, s.shop_name as target_shop_name
               FROM announcements a LEFT JOIN shops s ON a.target_shop_id = s.id
               WHERE a.id = ?""",
            (ann_id,)
        ).fetchone()

        result = dict(ann)
        result['responses'] = []
        result['total_targets'] = len(shops)
        result['sent_count'] = sent_count
        result['agree_count'] = 0
        result['acknowledge_count'] = 0
        result['disagree_count'] = 0
        result['responded_count'] = 0

        return jsonify(result), 201
    finally:
        db.close()


@announcement_bp.route('/api/announcements/<int:ann_id>/respond', methods=['POST'])
def respond_announcement(ann_id):
    """Called by Telegram bot callback - no auth required"""
    data = request.get_json()
    if not data or not data.get('shop_id') or not data.get('response'):
        return jsonify({'error': 'shop_id and response required'}), 400

    response_type = data['response']
    if response_type not in ('agree', 'acknowledge', 'disagree'):
        return jsonify({'error': 'Invalid response type'}), 400

    db = get_db()
    try:
        # Check if already responded
        existing = db.execute(
            "SELECT id FROM announcement_responses WHERE announcement_id = ? AND shop_id = ?",
            (ann_id, data['shop_id'])
        ).fetchone()

        if existing:
            # Update existing response
            db.execute(
                "UPDATE announcement_responses SET response = ?, responded_at = datetime('now') WHERE id = ?",
                (response_type, existing['id'])
            )
        else:
            db.execute(
                "INSERT INTO announcement_responses (announcement_id, shop_id, response) VALUES (?, ?, ?)",
                (ann_id, data['shop_id'], response_type)
            )
        db.commit()
        return jsonify({'message': 'Response recorded'})
    finally:
        db.close()


@announcement_bp.route('/api/announcements/<int:ann_id>', methods=['DELETE'])
@token_required
def delete_announcement(ann_id, current_user):
    db = get_db()
    try:
        db.execute("DELETE FROM announcement_responses WHERE announcement_id = ?", (ann_id,))
        db.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
        db.commit()
        return jsonify({'message': 'Announcement deleted'})
    finally:
        db.close()
