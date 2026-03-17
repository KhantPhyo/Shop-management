import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from config import Config
import sqlite3

logger = logging.getLogger(__name__)

# Conversation states for /create
SELECT_SHOP, ENTER_TITLE, ENTER_DESCRIPTION, SELECT_PRIORITY, ENTER_DEADLINE, SELECT_FINE, CONFIRM_CREATE = range(7)
# Conversation states for /modify
MODIFY_SELECT_FIELD, MODIFY_ENTER_VALUE, MODIFY_CONFIRM = range(7, 10)
# For /delete
DELETE_CONFIRM = 10

def get_db():
    db = sqlite3.connect(Config.DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db

class AdminBot:
    def __init__(self):
        self.app = None

    async def setup(self):
        if not Config.ADMIN_TELEGRAM_BOT_TOKEN or Config.ADMIN_TELEGRAM_BOT_TOKEN == 'your_admin_bot_token_from_botfather':
            logger.warning("Admin bot token not configured, skipping admin bot setup")
            return

        self.app = Application.builder().token(Config.ADMIN_TELEGRAM_BOT_TOKEN).build()

        # Create conversation handler
        create_conv = ConversationHandler(
            entry_points=[CommandHandler('create', self.create_start)],
            states={
                SELECT_SHOP: [CallbackQueryHandler(self.create_select_shop, pattern=r'^shop_\d+$')],
                ENTER_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_enter_title)],
                ENTER_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_enter_description)],
                SELECT_PRIORITY: [CallbackQueryHandler(self.create_select_priority, pattern=r'^priority_')],
                ENTER_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_enter_deadline)],
                SELECT_FINE: [CallbackQueryHandler(self.create_select_fine, pattern=r'^fine_')],
                CONFIRM_CREATE: [CallbackQueryHandler(self.create_confirm, pattern=r'^(confirm_create|cancel_create)$')],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        modify_conv = ConversationHandler(
            entry_points=[CommandHandler('modify', self.modify_start)],
            states={
                MODIFY_SELECT_FIELD: [CallbackQueryHandler(self.modify_select_field, pattern=r'^modify_')],
                MODIFY_ENTER_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.modify_enter_value)],
                MODIFY_CONFIRM: [CallbackQueryHandler(self.modify_confirm, pattern=r'^(confirm_modify|cancel_modify)$')],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        delete_conv = ConversationHandler(
            entry_points=[CommandHandler('delete', self.delete_start)],
            states={
                DELETE_CONFIRM: [CallbackQueryHandler(self.delete_confirm, pattern=r'^(confirm_delete|cancel_delete)$')],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        self.app.add_handler(create_conv)
        self.app.add_handler(modify_conv)
        self.app.add_handler(delete_conv)
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('help', self.help_cmd))
        self.app.add_handler(CommandHandler('today', self.today))
        self.app.add_handler(CommandHandler('shop', self.shop_tasks))
        self.app.add_handler(CommandHandler('shops', self.shops_list))
        self.app.add_handler(CommandHandler('overdue', self.overdue))
        self.app.add_handler(CommandHandler('fine', self.fine))
        self.app.add_handler(CommandHandler('stats', self.stats))
        self.app.add_handler(CommandHandler('remind', self.remind))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("Admin bot started")

    async def stop(self):
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    # --- Basic commands ---

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "\U0001f916 *Admin Task Bot*\n\n"
            "Available Commands:\n"
            "/create - Task \u1021\u101e\u1005\u103a\u1016\u1014\u103a\u1010\u102e\u1038\n"
            "/modify TASK-ID - Task \u1015\u103c\u1004\u103a\u1006\u1004\u103a\n"
            "/delete TASK-ID - Task \u1016\u103b\u1000\u103a\n"
            "/today [status] - \u1012\u102e\u1014\u1031\u1037 tasks\n"
            "/shop <name/id> - Shop tasks\n"
            "/shops - Shop \u1005\u102c\u101b\u1004\u103a\u1038\n"
            "/overdue - Overdue tasks\n"
            "/fine TASK-ID amount - \u1012\u100f\u103a\u1000\u103c\u1031\u1038\u1010\u1015\u103a\n"
            "/stats - Dashboard summary\n"
            "/remind TASK-ID - \u101e\u1010\u102d\u1015\u1031\u1038\n"
            "/help - \u1021\u101e\u1031\u1038\u1005\u102d\u1010\u103a",
            parse_mode='Markdown'
        )

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "\U0001f4d6 *Command Guide*\n\n"
            "*Task Management:*\n"
            "/create - Interactive task creation\n"
            "/modify TASK-20260317-0001 - Edit a task\n"
            "/delete TASK-20260317-0001 - Delete a task\n\n"
            "*Viewing:*\n"
            "/today - All today's tasks\n"
            "/today done - Today's completed tasks\n"
            "/today pending - Today's pending tasks\n"
            "/shop Shop1 - Tasks for specific shop\n"
            "/shops - All registered shops\n"
            "/overdue - All overdue tasks\n\n"
            "*Actions:*\n"
            "/fine TASK-ID 500 - Apply 500 MMK fine\n"
            "/remind TASK-ID - Send manual reminder\n"
            "/stats - Overall statistics",
            parse_mode='Markdown'
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("\u274c \u1015\u101a\u103a\u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038\u104b")
        return ConversationHandler.END

    # --- /create conversation ---

    async def create_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db = get_db()
        try:
            shops = db.execute("SELECT id, shop_name FROM shops WHERE is_active = 1").fetchall()
            if not shops:
                await update.message.reply_text("\u274c Active shop \u1019\u101b\u103e\u102d\u1015\u102b\u104b \u1021\u101b\u1004\u103a shop \u1011\u100a\u103a\u1037\u1015\u102b\u104b")
                return ConversationHandler.END

            buttons = [[InlineKeyboardButton(s['shop_name'], callback_data=f"shop_{s['id']}")] for s in shops]
            await update.message.reply_text("\U0001f3ea \u1006\u102d\u102f\u1004\u103a\u101b\u103d\u1031\u1038\u1015\u102b:", reply_markup=InlineKeyboardMarkup(buttons))
            return SELECT_SHOP
        finally:
            db.close()

    async def create_select_shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        shop_id = int(query.data.replace('shop_', ''))
        context.user_data['new_task'] = {'shop_id': shop_id}
        await query.edit_message_text("\U0001f4dd Task \u1001\u1031\u102b\u1004\u103a\u1038\u1005\u1005\u103a \u101b\u102d\u102f\u1000\u103a\u1015\u102b:")
        return ENTER_TITLE

    async def create_enter_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['new_task']['title'] = update.message.text
        await update.message.reply_text("\U0001f4c4 \u1021\u101e\u1031\u1038\u1005\u102d\u1010\u103a \u101b\u1031\u1038\u1015\u102b (skip \u101c\u102d\u102f\u1037 \u101b\u102d\u102f\u1000\u103a\u101c\u102d\u102f\u1037\u101b\u1015\u102b\u1010\u101a\u103a):")
        return ENTER_DESCRIPTION

    async def create_enter_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        context.user_data['new_task']['description'] = '' if text.lower() == 'skip' else text

        buttons = [
            [InlineKeyboardButton("\U0001f7e2 Low", callback_data="priority_low"),
             InlineKeyboardButton("\U0001f535 Medium", callback_data="priority_medium")],
            [InlineKeyboardButton("\U0001f7e0 High", callback_data="priority_high"),
             InlineKeyboardButton("\U0001f534 Urgent", callback_data="priority_urgent")]
        ]
        await update.message.reply_text("\u26a1 Priority \u101b\u103d\u1031\u1038\u1015\u102b:", reply_markup=InlineKeyboardMarkup(buttons))
        return SELECT_PRIORITY

    async def create_select_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        priority = query.data.replace('priority_', '')
        context.user_data['new_task']['priority'] = priority
        await query.edit_message_text("\U0001f4c5 Deadline \u101b\u102d\u102f\u1000\u103a\u1015\u102b (YYYY-MM-DD HH:MM) (none \u1006\u102d\u102f skip):")
        return ENTER_DEADLINE

    async def create_enter_deadline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        if text.lower() != 'none':
            context.user_data['new_task']['deadline'] = text

        buttons = [
            [InlineKeyboardButton("\u1019\u1010\u1015\u103a\u1018\u1030\u1038", callback_data="fine_0")],
            [InlineKeyboardButton("500 MMK", callback_data="fine_500"),
             InlineKeyboardButton("1000 MMK", callback_data="fine_1000")]
        ]
        await update.message.reply_text("\U0001f4b8 \u1012\u100f\u103a\u1000\u103c\u1031\u1038 (Deadline \u1000\u103b\u1031\u102c\u103a\u101b\u1004\u103a):", reply_markup=InlineKeyboardMarkup(buttons))
        return SELECT_FINE

    async def create_select_fine(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        fine = int(query.data.replace('fine_', ''))
        context.user_data['new_task']['fine_amount_mmk'] = fine

        task = context.user_data['new_task']
        db = get_db()
        try:
            shop = db.execute("SELECT shop_name FROM shops WHERE id = ?", (task['shop_id'],)).fetchone()
            shop_name = shop['shop_name'] if shop else 'Unknown'
        finally:
            db.close()

        priority_emoji = {'low': '\U0001f7e2', 'medium': '\U0001f535', 'high': '\U0001f7e0', 'urgent': '\U0001f534'}.get(task['priority'], '\u26aa')

        summary = (
            f"\U0001f4cb *Task \u1021\u101e\u1005\u103a \u1021\u1010\u100a\u103a\u1015\u103c\u102f\u1015\u102b*\n\n"
            f"\U0001f3ea \u1006\u102d\u102f\u1004\u103a: {shop_name}\n"
            f"\U0001f4dd \u1001\u1031\u102b\u1004\u103a\u1038\u1005\u1005\u103a: {task['title']}\n"
            f"\U0001f4c4 \u1021\u101e\u1031\u1038\u1005\u102d\u1010\u103a: {task.get('description', '-')}\n"
            f"\u26a1 Priority: {priority_emoji} {task['priority']}\n"
            f"\U0001f4c5 Deadline: {task.get('deadline', 'N/A')}\n"
            f"\U0001f4b8 \u1012\u100f\u103a\u1000\u103c\u1031\u1038: {fine} MMK"
        )

        buttons = [
            [InlineKeyboardButton("\u2705 Confirm", callback_data="confirm_create"),
             InlineKeyboardButton("\u274c Cancel", callback_data="cancel_create")]
        ]
        await query.edit_message_text(summary, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
        return CONFIRM_CREATE

    async def create_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'cancel_create':
            context.user_data.clear()
            await query.edit_message_text("\u274c \u1015\u101a\u103a\u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038\u104b")
            return ConversationHandler.END

        task_data = context.user_data['new_task']

        from task_utils import generate_task_id
        db = get_db()
        try:
            task_id = generate_task_id(db)
            db.execute(
                """INSERT INTO tasks (task_id, shop_id, title, description, priority, deadline, fine_amount_mmk, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'telegram')""",
                (task_id, task_data['shop_id'], task_data['title'], task_data.get('description', ''),
                 task_data['priority'], task_data.get('deadline'), task_data.get('fine_amount_mmk', 0))
            )
            task_db_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'created', 'admin')",
                (task_db_id,)
            )
            db.commit()

            await query.edit_message_text(f"\u2705 Task `{task_id}` \u1016\u1014\u103a\u1010\u102e\u1038\u1015\u103c\u102e\u1038!", parse_mode='Markdown')

            # Send notification to shop bot
            from tg_bots.shop_bot_manager import shop_bot_manager
            task_data['task_id'] = task_id
            try:
                await shop_bot_manager.send_task_notification(task_data['shop_id'], task_data)
            except Exception as e:
                logger.error(f"Failed to notify shop: {e}")

        finally:
            db.close()
            context.user_data.clear()

        return ConversationHandler.END

    # --- /modify conversation ---

    async def modify_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /modify TASK-20260317-0001")
            return ConversationHandler.END

        task_id_str = args[0]
        db = get_db()
        try:
            task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if not task:
                await update.message.reply_text(f"\u274c Task `{task_id_str}` \u101b\u103e\u102c\u1019\u1010\u103d\u1031\u1037\u1015\u102b\u104b")
                return ConversationHandler.END

            context.user_data['modify_task_id'] = task_id_str
            context.user_data['modify_db_id'] = task['id']

            buttons = [
                [InlineKeyboardButton("\U0001f4dd Title", callback_data="modify_title"),
                 InlineKeyboardButton("\U0001f4c4 Description", callback_data="modify_description")],
                [InlineKeyboardButton("\u26a1 Priority", callback_data="modify_priority"),
                 InlineKeyboardButton("\U0001f4c5 Deadline", callback_data="modify_deadline")],
                [InlineKeyboardButton("\u274c Cancel", callback_data="modify_cancel")]
            ]

            await update.message.reply_text(
                f"\u270f\ufe0f Task `{task_id_str}` \u1015\u103c\u1004\u103a\u1006\u1004\u103a\u1019\u101a\u103a\n\n\u1018\u102c\u1015\u103c\u1004\u103a\u1001\u103b\u1004\u103a\u1015\u102b\u101e\u101c\u1032:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return MODIFY_SELECT_FIELD
        finally:
            db.close()

    async def modify_select_field(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'modify_cancel':
            context.user_data.clear()
            await query.edit_message_text("\u274c \u1015\u101a\u103a\u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038\u104b")
            return ConversationHandler.END

        field = query.data.replace('modify_', '')
        context.user_data['modify_field'] = field

        if field == 'priority':
            buttons = [
                [InlineKeyboardButton("\U0001f7e2 Low", callback_data="confirm_modify"),
                 InlineKeyboardButton("\U0001f535 Medium", callback_data="confirm_modify")],
                [InlineKeyboardButton("\U0001f7e0 High", callback_data="confirm_modify"),
                 InlineKeyboardButton("\U0001f534 Urgent", callback_data="confirm_modify")]
            ]
            # Actually, let's just ask for text input for simplicity
            await query.edit_message_text(f"New {field} value \u101b\u102d\u102f\u1000\u103a\u1015\u102b:")
            return MODIFY_ENTER_VALUE

        await query.edit_message_text(f"New {field} value \u101b\u102d\u102f\u1000\u103a\u1015\u102b:")
        return MODIFY_ENTER_VALUE

    async def modify_enter_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_value = update.message.text
        field = context.user_data['modify_field']
        context.user_data['modify_value'] = new_value

        buttons = [
            [InlineKeyboardButton("\u2705 Confirm", callback_data="confirm_modify"),
             InlineKeyboardButton("\u274c Cancel", callback_data="cancel_modify")]
        ]
        await update.message.reply_text(
            f"\u270f\ufe0f {field} \u2192 {new_value}\n\n\u1021\u1010\u100a\u103a\u1015\u103c\u102f\u1019\u101c\u102c\u1038?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return MODIFY_CONFIRM

    async def modify_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'cancel_modify':
            context.user_data.clear()
            await query.edit_message_text("\u274c \u1015\u101a\u103a\u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038\u104b")
            return ConversationHandler.END

        field = context.user_data['modify_field']
        value = context.user_data['modify_value']
        task_id_str = context.user_data['modify_task_id']
        db_id = context.user_data['modify_db_id']

        # Only allow safe fields
        allowed = {'title', 'description', 'priority', 'deadline'}
        if field not in allowed:
            context.user_data.clear()
            await query.edit_message_text("Invalid field.")
            return ConversationHandler.END

        db = get_db()
        try:
            db.execute(f"UPDATE tasks SET {field}=?, updated_at=datetime('now') WHERE id=?", (value, db_id))
            db.execute(
                "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'edited', 'admin', ?)",
                (db_id, f'{{"field": "{field}", "new_value": "{value}"}}')
            )
            db.commit()

            await query.edit_message_text(f"\u2705 Task `{task_id_str}` \u1015\u103c\u1004\u103a\u1006\u1004\u103a\u1015\u103c\u102e\u1038!\n{field} \u2192 {value}", parse_mode='Markdown')

            # Notify shop
            task = db.execute("SELECT * FROM tasks WHERE id = ?", (db_id,)).fetchone()
            if task:
                from tg_bots.shop_bot_manager import shop_bot_manager
                await shop_bot_manager.send_message(
                    task['shop_id'],
                    f"\u270f\ufe0f *TASK \u1015\u103c\u1004\u103a\u1006\u1004\u103a\u1015\u103c\u102e\u1038*\n\nTask ID: `{task_id_str}`\n\u1015\u103c\u1031\u102c\u1004\u103a\u1038\u101c\u1032\u1001\u103b\u1000\u103a: {field} \u2192 {value}"
                )
        finally:
            db.close()
            context.user_data.clear()

        return ConversationHandler.END

    # --- /delete conversation ---

    async def delete_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /delete TASK-20260317-0001")
            return ConversationHandler.END

        task_id_str = args[0]
        db = get_db()
        try:
            task = db.execute(
                "SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id WHERE t.task_id = ?",
                (task_id_str,)
            ).fetchone()
            if not task:
                await update.message.reply_text(f"\u274c Task `{task_id_str}` \u101b\u103e\u102c\u1019\u1010\u103d\u1031\u1037\u1015\u102b\u104b")
                return ConversationHandler.END

            context.user_data['delete_task'] = dict(task)

            buttons = [
                [InlineKeyboardButton("\u2705 \u1016\u103b\u1000\u103a\u1019\u101a\u103a", callback_data="confirm_delete"),
                 InlineKeyboardButton("\u274c \u1019\u1016\u103b\u1000\u103a\u1018\u1030\u1038", callback_data="cancel_delete")]
            ]
            await update.message.reply_text(
                f"\U0001f5d1\ufe0f Task \u1016\u103b\u1000\u103a\u1019\u101c\u102c\u1038?\n\n"
                f"Task ID: `{task_id_str}`\n"
                f"Title: {task['title']}\n"
                f"Shop: {task['shop_name']}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return DELETE_CONFIRM
        finally:
            db.close()

    async def delete_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'cancel_delete':
            context.user_data.clear()
            await query.edit_message_text("\u274c \u1015\u101a\u103a\u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038\u104b")
            return ConversationHandler.END

        task = context.user_data['delete_task']

        db = get_db()
        try:
            db.execute("INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'deleted', 'admin')", (task['id'],))
            db.execute("DELETE FROM tasks WHERE id = ?", (task['id'],))
            db.commit()

            await query.edit_message_text(f"\U0001f5d1\ufe0f Task `{task['task_id']}` \u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038!", parse_mode='Markdown')

            from tg_bots.shop_bot_manager import shop_bot_manager
            await shop_bot_manager.send_message(
                task['shop_id'],
                f"\U0001f5d1\ufe0f *TASK \u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038*\n\nTask ID: `{task['task_id']}`\n\u1001\u1031\u102b\u1004\u103a\u1038\u1005\u1005\u103a: {task['title']}\n\nAdmin \u1000 \u1016\u103b\u1000\u103a\u101c\u102d\u102f\u1000\u103a\u1015\u102b\u1015\u103c\u102e\u104b"
            )
        finally:
            db.close()
            context.user_data.clear()

        return ConversationHandler.END

    # --- Simple commands ---

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status_filter = context.args[0] if context.args else None

        db = get_db()
        try:
            sql = """SELECT t.*, s.shop_name FROM tasks t
                     JOIN shops s ON t.shop_id = s.id
                     WHERE date(t.created_at) = date('now')"""
            params = []

            if status_filter:
                sql += " AND t.status = ?"
                params.append(status_filter)

            sql += " ORDER BY t.created_at DESC"
            tasks = db.execute(sql, params).fetchall()

            if not tasks:
                await update.message.reply_text(f"\U0001f4cb \u1012\u102e\u1014\u1031\u1037 task \u1019\u101b\u103e\u102d\u1015\u102b\u104b {f'(filter: {status_filter})' if status_filter else ''}")
                return

            status_emoji = {'pending': '\u23f3', 'accepted': '\u2705', 'rejected': '\u274c', 'in_progress': '\U0001f504', 'done': '\u2705', 'overdue': '\u26a0\ufe0f'}

            lines = [f"\U0001f4cb *Today's Tasks* {f'({status_filter})' if status_filter else ''}\n"]
            for i, t in enumerate(tasks, 1):
                emoji = status_emoji.get(t['status'], '\u2753')
                lines.append(f"{i}. `{t['task_id']}` | {t['shop_name']} | {emoji} {t['status']}")

            await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')
        finally:
            db.close()

    async def shop_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /shop <shop_name or shop_id>")
            return

        query_str = ' '.join(context.args)
        db = get_db()
        try:
            # Try by ID first, then by name
            shop = None
            try:
                shop = db.execute("SELECT * FROM shops WHERE id = ?", (int(query_str),)).fetchone()
            except ValueError:
                shop = db.execute("SELECT * FROM shops WHERE shop_name LIKE ?", (f'%{query_str}%',)).fetchone()

            if not shop:
                await update.message.reply_text(f"\u274c Shop '{query_str}' \u101b\u103e\u102c\u1019\u1010\u103d\u1031\u1037\u1015\u102b\u104b")
                return

            tasks = db.execute(
                """SELECT * FROM tasks WHERE shop_id = ? AND status NOT IN ('done')
                   ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END""",
                (shop['id'],)
            ).fetchall()

            priority_emoji = {'low': '\U0001f7e2', 'medium': '\U0001f535', 'high': '\U0001f7e0', 'urgent': '\U0001f534'}

            lines = [f"\U0001f3ea *Tasks for {shop['shop_name']}*\n"]
            if not tasks:
                lines.append("Active task \u1019\u101b\u103e\u102d\u1015\u102b\u104b")
            else:
                for i, t in enumerate(tasks, 1):
                    pe = priority_emoji.get(t['priority'], '\u26aa')
                    lines.append(f"{i}. `{t['task_id']}` | {pe} {t['priority']} | {t['status']} | DL: {t['deadline'] or 'N/A'}")

            await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')
        finally:
            db.close()

    async def shops_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db = get_db()
        try:
            shops = db.execute(
                """SELECT s.*, COUNT(CASE WHEN t.status NOT IN ('done') THEN 1 END) as active_tasks
                   FROM shops s LEFT JOIN tasks t ON s.id = t.shop_id
                   WHERE s.is_active = 1 GROUP BY s.id ORDER BY s.shop_name"""
            ).fetchall()

            if not shops:
                await update.message.reply_text("\U0001f3ea Shop \u1019\u101b\u103e\u102d\u1015\u102b\u104b")
                return

            lines = ["\U0001f3ea *Registered Shops*\n"]
            for i, s in enumerate(shops, 1):
                lines.append(f"{i}. {s['shop_name']} - Leader: {s['leader_name']} - Active Tasks: {s['active_tasks']}")

            await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')
        finally:
            db.close()

    async def overdue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db = get_db()
        try:
            tasks = db.execute(
                """SELECT t.*, s.shop_name FROM tasks t JOIN shops s ON t.shop_id = s.id
                   WHERE t.status = 'overdue' ORDER BY t.deadline"""
            ).fetchall()

            if not tasks:
                await update.message.reply_text("\u2705 Overdue task \u1019\u101b\u103e\u102d\u1015\u102b\u104b")
                return

            lines = ["\u26a0\ufe0f *Overdue Tasks*\n"]
            for i, t in enumerate(tasks, 1):
                lines.append(f"{i}. `{t['task_id']}` | {t['shop_name']} | DL: {t['deadline']} | Fine: {t['fine_amount_mmk']} MMK")

            await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')
        finally:
            db.close()

    async def fine(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /fine TASK-20260317-0001 500")
            return

        task_id_str = context.args[0]
        try:
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("\u274c Amount must be a number (500 or 1000)")
            return

        db = get_db()
        try:
            task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if not task:
                await update.message.reply_text(f"\u274c Task `{task_id_str}` \u101b\u103e\u102c\u1019\u1010\u103d\u1031\u1037\u1015\u102b\u104b")
                return

            db.execute("UPDATE tasks SET fine_amount_mmk = ?, updated_at = datetime('now') WHERE id = ?", (amount, task['id']))
            db.execute(
                "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'fined', 'admin', ?)",
                (task['id'], f'{{"amount": {amount}}}')
            )
            db.commit()

            await update.message.reply_text(f"\U0001f4b8 Task `{task_id_str}` \u1012\u100f\u103a\u1000\u103c\u1031\u1038 {amount} MMK \u1010\u1015\u103a\u1015\u103c\u102e\u1038!", parse_mode='Markdown')

            from tg_bots.shop_bot_manager import shop_bot_manager
            task_dict = dict(task)
            task_dict['fine_amount_mmk'] = amount
            await shop_bot_manager.send_fine_notification(task['shop_id'], task_dict)
        finally:
            db.close()

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db = get_db()
        try:
            today_stats = db.execute(
                """SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status='overdue' THEN 1 ELSE 0 END) as overdue,
                    SUM(fine_amount_mmk) as total_fines
                FROM tasks WHERE date(created_at) = date('now')"""
            ).fetchone()

            # Fastest shop
            fastest = db.execute(
                """SELECT s.shop_name, AVG((julianday(t.completed_at) - julianday(t.created_at)) * 24) as avg_hrs
                   FROM tasks t JOIN shops s ON t.shop_id = s.id
                   WHERE t.status = 'done' AND t.completed_at IS NOT NULL
                   GROUP BY t.shop_id ORDER BY avg_hrs ASC LIMIT 1"""
            ).fetchone()

            msg = (
                f"\U0001f4ca *Dashboard Summary*\n\n"
                f"Today: {today_stats['total'] or 0} tasks\n"
                f"\u2705 Done: {today_stats['done'] or 0}\n"
                f"\u23f3 Pending: {today_stats['pending'] or 0}\n"
                f"\U0001f504 In Progress: {today_stats['in_progress'] or 0}\n"
                f"\u26a0\ufe0f Overdue: {today_stats['overdue'] or 0}\n"
            )

            if fastest:
                msg += f"\n\U0001f3c6 Fastest: {fastest['shop_name']} (avg {fastest['avg_hrs']:.1f} hrs)"

            msg += f"\n\U0001f4b8 Total Fines: {today_stats['total_fines'] or 0} MMK"

            await update.message.reply_text(msg, parse_mode='Markdown')
        finally:
            db.close()

    async def remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /remind TASK-20260317-0001")
            return

        task_id_str = context.args[0]
        db = get_db()
        try:
            task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if not task:
                await update.message.reply_text(f"\u274c Task `{task_id_str}` \u101b\u103e\u102c\u1019\u1010\u103d\u1031\u1037\u1015\u102b\u104b")
                return

            from tg_bots.shop_bot_manager import shop_bot_manager
            await shop_bot_manager.send_reminder(task['shop_id'], dict(task))

            db.execute(
                "UPDATE tasks SET reminder_count = reminder_count + 1, last_reminder_at = datetime('now') WHERE id = ?",
                (task['id'],)
            )
            db.execute(
                "INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'reminded', 'admin')",
                (task['id'],)
            )
            db.commit()

            await update.message.reply_text(f"\u23f0 Task `{task_id_str}` \u101e\u1010\u102d\u1015\u1031\u1038\u1015\u102d\u102f\u1037\u1015\u103c\u102e\u1038!", parse_mode='Markdown')
        finally:
            db.close()


admin_bot = AdminBot()
