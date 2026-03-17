import asyncio
import logging
import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ConversationHandler
from config import Config

logger = logging.getLogger(__name__)

# Conversation states for report collection
COLLECTING_REPORT = 0

class ShopBotManager:
    def __init__(self):
        self.bots = {}  # {shop_id: {'app': Application, 'bot': Bot, 'token': str, 'chat_id': str}}
        self.loop = None

    def set_loop(self, loop):
        self.loop = loop

    async def register_shop_bot(self, shop_id, token, chat_id):
        """Register and start a new bot for a shop"""
        if shop_id in self.bots:
            await self.stop_shop_bot(shop_id)

        try:
            app = Application.builder().token(token).build()

            # Add handlers for shop leader interactions
            # Accept task callback
            app.add_handler(CallbackQueryHandler(self._handle_accept, pattern=r'^accept_'))
            # Reject task callback
            app.add_handler(CallbackQueryHandler(self._handle_reject_start, pattern=r'^reject_'))
            # In progress callback
            app.add_handler(CallbackQueryHandler(self._handle_in_progress, pattern=r'^inprogress_'))
            # Done callback - starts report collection
            app.add_handler(CallbackQueryHandler(self._handle_done_start, pattern=r'^done_'))

            # Announcement response callbacks
            app.add_handler(CallbackQueryHandler(self._handle_announcement_response, pattern=r'^ann_(agree|ack|disagree)_'))

            # Report collection conversation handler
            report_conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(self._handle_done_start, pattern=r'^done_')],
                states={
                    COLLECTING_REPORT: [
                        MessageHandler(filters.PHOTO, self._handle_report_photo),
                        MessageHandler(filters.Document.ALL, self._handle_report_document),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_report_text),
                        CommandHandler('finish', self._handle_finish_report),
                    ]
                },
                fallbacks=[CommandHandler('cancel', self._handle_cancel)],
                per_message=False,
            )
            # Note: The ConversationHandler above would override the simple done_ handler.
            # For simplicity, we'll handle done flow without ConversationHandler in this version.

            # Start command
            app.add_handler(CommandHandler('start', self._handle_start))
            app.add_handler(CommandHandler('finish', self._handle_finish_report))

            # Message handlers for report collection (photos, documents, text during active report)
            app.add_handler(MessageHandler(filters.PHOTO, self._handle_report_photo))
            app.add_handler(MessageHandler(filters.Document.ALL, self._handle_report_document))

            await app.initialize()
            await app.start()

            # Start polling in background
            await app.updater.start_polling(drop_pending_updates=True)

            self.bots[shop_id] = {
                'app': app,
                'token': token,
                'chat_id': chat_id,
                'active_reports': {}  # {task_id: True} tracks which tasks are in report mode
            }

            logger.info(f"Shop bot registered for shop_id={shop_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register bot for shop_id={shop_id}: {e}")
            return False

    async def stop_shop_bot(self, shop_id):
        """Stop a shop's bot"""
        if shop_id in self.bots:
            try:
                app = self.bots[shop_id]['app']
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
                del self.bots[shop_id]
                logger.info(f"Shop bot stopped for shop_id={shop_id}")
            except Exception as e:
                logger.error(f"Error stopping bot for shop_id={shop_id}: {e}")

    async def send_task_notification(self, shop_id, task_data):
        """Send new task notification to shop's Telegram"""
        if shop_id not in self.bots:
            logger.warning(f"No bot registered for shop_id={shop_id}")
            return False

        bot_info = self.bots[shop_id]
        bot = Bot(token=bot_info['token'])
        chat_id = bot_info['chat_id']

        priority_emoji = {'low': '\U0001f7e2', 'medium': '\U0001f535', 'high': '\U0001f7e0', 'urgent': '\U0001f534'}.get(task_data.get('priority', 'medium'), '\u26aa')

        message = (
            f"\U0001f4cb *TASK \u1021\u101e\u1005\u103a\u101b\u1031\u102c\u1000\u103a\u1015\u102b\u1015\u103c\u102e*\n\n"
            f"Task ID: `{task_data['task_id']}`\n"
            f"\u1001\u1031\u102b\u1004\u103a\u1038\u1005\u1005\u103a: {task_data['title']}\n"
            f"\u1021\u1000\u103c\u1031\u102c\u1004\u103a\u1038\u1021\u101b\u102c: {task_data.get('description', '-')}\n"
            f"Priority: {priority_emoji} {task_data.get('priority', 'medium')}\n"
            f"Deadline: {task_data.get('deadline', 'N/A')}\n"
            f"\u1012\u100f\u103a\u1000\u103c\u1031\u1038 (\u1000\u103b\u1031\u102c\u103a\u101b\u1004\u103a): {task_data.get('fine_amount_mmk', 0)} MMK\n"
            f"Report: {self._format_report_type(task_data.get('required_report_type', 'photo'))}\n\n"
            f"\u1041 \u1014\u102c\u101b\u102e\u1021\u1010\u103d\u1004\u103a\u1038 \u101c\u1000\u103a\u1001\u1036\u1015\u102b\u104b"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("\u2705 \u101c\u1000\u103a\u1001\u1036\u1019\u101a\u103a", callback_data=f"accept_{task_data['task_id']}"),
                InlineKeyboardButton("\u274c \u1004\u103c\u1004\u103a\u1038\u1019\u101a\u103a", callback_data=f"reject_{task_data['task_id']}")
            ]
        ])

        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown', reply_markup=keyboard)
            return True
        except Exception as e:
            logger.error(f"Failed to send task notification to shop_id={shop_id}: {e}")
            return False

    async def send_reminder(self, shop_id, task_data):
        """Send reminder to shop"""
        if shop_id not in self.bots:
            return False

        bot_info = self.bots[shop_id]
        bot = Bot(token=bot_info['token'])

        from task_utils import calculate_time_remaining
        time_remaining = calculate_time_remaining(task_data.get('deadline'))

        message = (
            f"\u23f0 *\u101e\u1010\u102d\u1015\u1031\u1038\u1001\u103b\u1000\u103a*\n\n"
            f"Task `{task_data['task_id']}` - {task_data['title']}\n"
            f"Status: {task_data['status']}\n"
            f"Deadline: {task_data.get('deadline', 'N/A')}\n"
            f"\u1000\u103b\u1014\u103a\u1001\u103b\u102d\u1014\u103a: {time_remaining}\n\n"
            f"\u26a0\ufe0f \u1021\u1019\u103c\u1014\u103a\u1006\u102f\u1036\u1038\u101c\u102f\u1015\u103a\u1015\u102b!"
        )

        buttons = []
        if task_data['status'] == 'pending':
            buttons.append(InlineKeyboardButton("\u2705 \u101c\u1000\u103a\u1001\u1036\u1019\u101a\u103a", callback_data=f"accept_{task_data['task_id']}"))
        if task_data['status'] in ('pending', 'accepted'):
            buttons.append(InlineKeyboardButton("\U0001f504 \u101c\u102f\u1015\u103a\u1014\u1031\u1015\u103c\u102e", callback_data=f"inprogress_{task_data['task_id']}"))
        buttons.append(InlineKeyboardButton("\u2705 \u1015\u103c\u102e\u1038\u1015\u103c\u102e", callback_data=f"done_{task_data['task_id']}"))

        keyboard = InlineKeyboardMarkup([buttons])

        try:
            await bot.send_message(chat_id=bot_info['chat_id'], text=message, parse_mode='Markdown', reply_markup=keyboard)
            return True
        except Exception as e:
            logger.error(f"Failed to send reminder to shop_id={shop_id}: {e}")
            return False

    async def send_message(self, shop_id, message):
        """Send a generic message to a shop"""
        if shop_id not in self.bots:
            return False
        bot_info = self.bots[shop_id]
        bot = Bot(token=bot_info['token'])
        try:
            await bot.send_message(chat_id=bot_info['chat_id'], text=message, parse_mode='Markdown')
            return True
        except Exception as e:
            logger.error(f"Failed to send message to shop_id={shop_id}: {e}")
            return False

    async def send_fine_notification(self, shop_id, task_data):
        """Send fine notification"""
        if shop_id not in self.bots:
            return False
        bot_info = self.bots[shop_id]
        bot = Bot(token=bot_info['token'])

        message = (
            f"\U0001f4b8 *\u1012\u100f\u103a\u1000\u103c\u1031\u1038\u1010\u1015\u103a\u1015\u103c\u102e\u1038*\n\n"
            f"Task ID: `{task_data['task_id']}`\n"
            f"\u1001\u1031\u102b\u1004\u103a\u1038\u1005\u1005\u103a: {task_data['title']}\n"
            f"\u1012\u100f\u103a\u1000\u103c\u1031\u1038: {task_data['fine_amount_mmk']} MMK\n"
            f"\u1021\u1000\u103c\u1031\u102c\u1004\u103a\u1038\u1015\u103c\u1001\u103b\u1000\u103a: Deadline \u1000\u103b\u1031\u102c\u103a\n\n"
            f"\u1021\u1019\u103c\u1014\u103a\u1006\u102f\u1036\u1038\u1015\u103c\u102e\u1038\u1021\u1031\u102c\u1004\u103a\u101c\u102f\u1015\u103a\u1015\u102b\u104b"
        )

        try:
            await bot.send_message(chat_id=bot_info['chat_id'], text=message, parse_mode='Markdown')
            return True
        except Exception as e:
            logger.error(f"Failed to send fine notification: {e}")
            return False

    @staticmethod
    def _format_report_type(report_type):
        """Format required report type for display"""
        if not report_type:
            return 'Any'
        type_labels = {
            'photo': '\U0001f4f8 Photo',
            'excel': '\U0001f4ca Excel',
            'file': '\U0001f4c4 File',
            'text': '\U0001f4ac Text'
        }
        types = [t.strip() for t in report_type.split(',')]
        return ', '.join(type_labels.get(t, t) for t in types)

    # --- Callback handlers for shop leader interactions ---

    async def _handle_start(self, update, context):
        await update.message.reply_text(
            "\U0001f3ea Shop Task Bot \u1019\u103e \u1000\u103c\u102d\u102f\u1006\u102d\u102f\u1015\u102b\u1010\u101a\u103a!\n\n"
            "Task \u1019\u103b\u102c\u1038\u1000\u102d\u102f \u1012\u102e bot \u1000\u1010\u1006\u1004\u103a\u1037 \u101c\u1000\u103a\u1001\u1036/\u1004\u103c\u1004\u103a\u1038\u1006\u102d\u102f/report \u1010\u1004\u103a\u1014\u102d\u102f\u1004\u103a\u1015\u102b\u1010\u101a\u103a\u104b\n"
            "Admin \u1000 task \u1015\u102d\u102f\u1037\u101c\u102c\u101b\u1004\u103a notification \u101b\u1015\u102b\u1019\u101a\u103a\u104b"
        )

    async def _handle_accept(self, update, context):
        """Handle task acceptance"""
        query = update.callback_query
        await query.answer()

        task_id_str = query.data.replace('accept_', '')

        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        db.row_factory = sqlite3.Row

        try:
            task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if not task:
                await query.edit_message_text("\u274c Task \u101b\u103e\u102c\u1019\u1010\u103d\u1031\u1037\u1015\u102b\u104b")
                return

            if task['status'] not in ('pending',):
                await query.edit_message_text(f"Task status: {task['status']} - \u101c\u1000\u103a\u1001\u1036\u101c\u102d\u102f\u1037\u1019\u101b\u1015\u102b\u104b")
                return

            db.execute(
                "UPDATE tasks SET status='accepted', accepted_at=datetime('now'), updated_at=datetime('now') WHERE task_id=?",
                (task_id_str,)
            )
            db.execute(
                "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'accepted', 'shop_leader', NULL)",
                (task['id'],)
            )
            db.commit()

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("\U0001f504 \u101c\u102f\u1015\u103a\u1014\u1031\u1015\u103c\u102e", callback_data=f"inprogress_{task_id_str}"),
                    InlineKeyboardButton("\u2705 \u1015\u103c\u102e\u1038\u1015\u103c\u102e", callback_data=f"done_{task_id_str}")
                ]
            ])

            await query.edit_message_text(
                f"\u2705 Task `{task_id_str}` \u101c\u1000\u103a\u1001\u1036\u1015\u103c\u102e\u1038! \u1005\u101c\u102f\u1015\u103a\u1015\u102b\u104b\n\n"
                f"\u101c\u102f\u1015\u103a\u1014\u1031\u1015\u103c\u102e\u1006\u102d\u102f '\u101c\u102f\u1015\u103a\u1014\u1031\u1015\u103c\u102e' \u1014\u103e\u102d\u1015\u103a\u1015\u102b\u104b\n"
                f"\u1015\u103c\u102e\u1038\u101b\u1004\u103a '\u1015\u103c\u102e\u1038\u1015\u103c\u102e' \u1014\u103e\u102d\u1015\u103a\u1015\u103c\u102e\u1038 report \u1010\u1004\u103a\u1015\u102b\u104b",
                parse_mode='Markdown',
                reply_markup=keyboard
            )

            # Notify admin
            await self._notify_admin(f"\u2705 Task `{task_id_str}` \u1000\u102d\u102f \u101c\u1000\u103a\u1001\u1036\u1015\u103c\u102e")

        finally:
            db.close()

    async def _handle_reject_start(self, update, context):
        """Handle task rejection"""
        query = update.callback_query
        await query.answer()

        task_id_str = query.data.replace('reject_', '')
        context.user_data['rejecting_task'] = task_id_str

        await query.edit_message_text(
            f"Task `{task_id_str}` \u1004\u103c\u1004\u103a\u1038\u1006\u102d\u102f\u1010\u1032\u1037 \u1021\u1000\u103c\u1031\u102c\u1004\u103a\u1038\u1015\u103c\u1001\u103b\u1000\u103a \u101b\u1031\u1038\u1015\u102b:",
            parse_mode='Markdown'
        )
        # The next text message from this user will be treated as rejection reason
        # We store the state in context.user_data

    async def _handle_in_progress(self, update, context):
        """Mark task as in progress"""
        query = update.callback_query
        await query.answer()

        task_id_str = query.data.replace('inprogress_', '')

        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        db.row_factory = sqlite3.Row

        try:
            task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if not task:
                await query.edit_message_text("\u274c Task \u101b\u103e\u102c\u1019\u1010\u103d\u1031\u1037\u1015\u102b\u104b")
                return

            db.execute(
                "UPDATE tasks SET status='in_progress', started_at=datetime('now'), updated_at=datetime('now') WHERE task_id=?",
                (task_id_str,)
            )
            db.execute(
                "INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'in_progress', 'shop_leader')",
                (task['id'],)
            )
            db.commit()

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("\u2705 \u1015\u103c\u102e\u1038\u1015\u103c\u102e", callback_data=f"done_{task_id_str}")]
            ])

            await query.edit_message_text(
                f"\U0001f504 Task `{task_id_str}` \u101c\u102f\u1015\u103a\u1014\u1031\u1015\u103c\u102e\u101c\u102d\u102f\u1037 \u1019\u103e\u1010\u103a\u1015\u103c\u102e\u1038!\n\n"
                f"\u1015\u103c\u102e\u1038\u101b\u1004\u103a '\u1015\u103c\u102e\u1038\u1015\u103c\u102e' \u1014\u103e\u102d\u1015\u103a\u1015\u103c\u102e\u1038 report \u1010\u1004\u103a\u1015\u102b\u104b",
                parse_mode='Markdown',
                reply_markup=keyboard
            )

            await self._notify_admin(f"\U0001f504 Task `{task_id_str}` \u101c\u102f\u1015\u103a\u1014\u1031\u1015\u103c\u102e")

        finally:
            db.close()

    async def _handle_done_start(self, update, context):
        """Start report collection when task marked done"""
        query = update.callback_query
        await query.answer()

        task_id_str = query.data.replace('done_', '')
        context.user_data['reporting_task'] = task_id_str

        await query.edit_message_text(
            f"📝 Task `{task_id_str}` Report တင်ပါ။\n\n"
            f"အောက်ပါတွေ ပို့လို့ရပါတယ်:\n"
            f"- 📸 ဓာတ်ပုံ (တစ်ပုံ/အများကြီး)\n"
            f"- 📄 ဖိုင် (Excel, PDF, etc.)\n"
            f"- 💬 စာသား ရေးပြီးပို့ပါ\n\n"
            f"အားလုံးပို့ပြီးရင် /finish ရိုက်ပါ။",
            parse_mode='Markdown'
        )

    async def _handle_report_photo(self, update, context):
        """Handle photo report submission"""
        task_id_str = context.user_data.get('reporting_task')
        if not task_id_str:
            return

        photo = update.message.photo[-1]  # Get highest resolution
        file = await photo.get_file()

        # Create upload directory
        upload_dir = os.path.join(Config.UPLOAD_DIR, task_id_str)
        os.makedirs(upload_dir, exist_ok=True)

        file_name = f"photo_{photo.file_unique_id}.jpg"
        file_path = os.path.join(upload_dir, file_name)
        await file.download_to_drive(file_path)

        # Save to DB
        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        try:
            task = db.execute("SELECT id FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if task:
                db.execute(
                    "INSERT INTO task_reports (task_id, report_type, file_path, file_name) VALUES (?, 'photo', ?, ?)",
                    (task[0], file_path, file_name)
                )
                db.commit()
        finally:
            db.close()

        await update.message.reply_text("\U0001f4f8 \u1013\u102c\u1010\u103a\u1015\u102f\u1036 \u101c\u1000\u103a\u1001\u1036\u1015\u103c\u102e\u1038! \u1014\u1031\u102c\u1000\u103a\u1011\u1015\u103a \u1015\u102d\u102f\u1037\u101c\u102d\u102f\u1037\u101b\u1015\u102b\u1010\u101a\u103a\u104b \u1015\u103c\u102e\u1038\u101b\u1004\u103a /finish")

    async def _handle_report_document(self, update, context):
        """Handle document report submission"""
        task_id_str = context.user_data.get('reporting_task')
        if not task_id_str:
            return

        doc = update.message.document
        file = await doc.get_file()

        upload_dir = os.path.join(Config.UPLOAD_DIR, task_id_str)
        os.makedirs(upload_dir, exist_ok=True)

        file_name = doc.file_name or f"file_{doc.file_unique_id}"
        file_path = os.path.join(upload_dir, file_name)
        await file.download_to_drive(file_path)

        # Determine report type
        ext = os.path.splitext(file_name)[1].lower()
        report_type = 'excel' if ext in ('.xlsx', '.xls', '.csv') else 'file'

        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        try:
            task = db.execute("SELECT id FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if task:
                db.execute(
                    "INSERT INTO task_reports (task_id, report_type, file_path, file_name) VALUES (?, ?, ?, ?)",
                    (task[0], report_type, file_path, file_name)
                )
                db.commit()
        finally:
            db.close()

        await update.message.reply_text(f"\U0001f4c4 \u1016\u102d\u102f\u1004\u103a `{file_name}` \u101c\u1000\u103a\u1001\u1036\u1015\u103c\u102e\u1038! \u1014\u1031\u102c\u1000\u103a\u1011\u1015\u103a \u1015\u102d\u102f\u1037\u101c\u102d\u102f\u1037\u101b\u1015\u102b\u1010\u101a\u103a\u104b \u1015\u103c\u102e\u1038\u101b\u1004\u103a /finish")

    async def _handle_report_text(self, update, context):
        """Handle text report or rejection reason"""
        # Check if this is a rejection reason
        rejecting_task = context.user_data.get('rejecting_task')
        if rejecting_task:
            task_id_str = rejecting_task
            reason = update.message.text
            del context.user_data['rejecting_task']

            import sqlite3
            db = sqlite3.connect(Config.DATABASE_PATH)
            try:
                task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
                if task:
                    db.execute(
                        "UPDATE tasks SET status='rejected', rejection_reason=?, updated_at=datetime('now') WHERE task_id=?",
                        (reason, task_id_str)
                    )
                    db.execute(
                        "INSERT INTO task_logs (task_id, action, actor, details) VALUES (?, 'rejected', 'shop_leader', ?)",
                        (task['id'], reason)
                    )
                    db.commit()
                    await update.message.reply_text(f"\u274c Task `{task_id_str}` \u1004\u103c\u1004\u103a\u1038\u1006\u102d\u102f\u1015\u103c\u102e\u1038\u104b\n\u1021\u1000\u103c\u1031\u102c\u1004\u103a\u1038\u1015\u103c\u1001\u103b\u1000\u103a: {reason}")
                    await self._notify_admin(f"\u274c Task `{task_id_str}` \u1004\u103c\u1004\u103a\u1038\u1006\u102d\u102f\u1015\u103c\u102e - \u1021\u1000\u103c\u1031\u102c\u1004\u103a\u1038\u1015\u103c\u1001\u103b\u1000\u103a: {reason}")
            finally:
                db.close()
            return

        # Check if collecting report
        task_id_str = context.user_data.get('reporting_task')
        if not task_id_str:
            return

        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        try:
            task = db.execute("SELECT id FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if task:
                db.execute(
                    "INSERT INTO task_reports (task_id, report_type, text_content) VALUES (?, 'text', ?)",
                    (task[0], update.message.text)
                )
                db.commit()
        finally:
            db.close()

        await update.message.reply_text("\U0001f4ac \u1005\u102c\u101e\u102c\u1038 \u101c\u1000\u103a\u1001\u1036\u1015\u103c\u102e\u1038! \u1014\u1031\u102c\u1000\u103a\u1011\u1015\u103a \u1015\u102d\u102f\u1037\u101c\u102d\u102f\u1037\u101b\u1015\u102b\u1010\u101a\u103a\u104b \u1015\u103c\u102e\u1038\u101b\u1004\u103a /finish")

    async def _handle_finish_report(self, update, context):
        """Finish report submission and mark task done"""
        task_id_str = context.user_data.get('reporting_task')
        if not task_id_str:
            await update.message.reply_text("Report တင်နေတဲ့ task မရှိပါ။")
            return

        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        db.row_factory = sqlite3.Row
        try:
            task = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id_str,)).fetchone()
            if task:
                # Mark task as done
                db.execute(
                    "UPDATE tasks SET status='done', completed_at=datetime('now'), updated_at=datetime('now') WHERE task_id=?",
                    (task_id_str,)
                )
                db.execute(
                    "INSERT INTO task_logs (task_id, action, actor) VALUES (?, 'done', 'shop_leader')",
                    (task['id'],)
                )
                db.commit()

                report_count = db.execute(
                    "SELECT COUNT(*) FROM task_reports WHERE task_id = ?", (task['id'],)
                ).fetchone()[0]

                await update.message.reply_text(
                    f"✅ Task `{task_id_str}` ပြီးပြီလို့ မှတ်တမ်းတင်ပြီး!\n"
                    f"📎 Report: {report_count} items\n\n"
                    f"ကျေးဇူးတင်ပါတယ်! 🙏",
                    parse_mode='Markdown'
                )

                del context.user_data['reporting_task']

                await self._notify_admin(f"✅ Task `{task_id_str}` ပြီးပြီ! 📎 Report: {report_count} items")
        finally:
            db.close()

    async def _handle_announcement_response(self, update, context):
        """Handle announcement agree/acknowledge/disagree"""
        query = update.callback_query
        await query.answer()

        data = query.data  # e.g. ann_agree_5, ann_ack_5, ann_disagree_5
        parts = data.split('_')
        response_type = parts[1]  # agree, ack, disagree
        ann_id = int(parts[2])

        # Map 'ack' to 'acknowledge'
        response_map = {'agree': 'agree', 'ack': 'acknowledge', 'disagree': 'disagree'}
        response = response_map.get(response_type, response_type)

        # Find which shop this bot belongs to
        shop_id = None
        for sid, bot_info in self.bots.items():
            if bot_info['chat_id'] == str(query.message.chat_id):
                shop_id = sid
                break

        if not shop_id:
            await query.edit_message_text("Error: Shop not found.")
            return

        # Save response to DB
        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        db.row_factory = sqlite3.Row
        try:
            existing = db.execute(
                "SELECT id FROM announcement_responses WHERE announcement_id = ? AND shop_id = ?",
                (ann_id, shop_id)
            ).fetchone()

            if existing:
                db.execute(
                    "UPDATE announcement_responses SET response = ?, responded_at = datetime('now') WHERE id = ?",
                    (response, existing['id'])
                )
            else:
                db.execute(
                    "INSERT INTO announcement_responses (announcement_id, shop_id, response) VALUES (?, ?, ?)",
                    (ann_id, shop_id, response)
                )
            db.commit()

            response_emoji = {'agree': '✅', 'acknowledge': '👁', 'disagree': '❌'}
            response_label = {'agree': 'Agree', 'acknowledge': 'Acknowledge', 'disagree': 'Disagree'}

            await query.edit_message_text(
                f"{query.message.text}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{response_emoji.get(response, '')} သင့်အဖြေ: **{response_label.get(response, response)}**\n"
                f"ကျေးဇူးတင်ပါတယ်! 🙏",
                parse_mode='Markdown'
            )

            await self._notify_admin(
                f"📢 Announcement #{ann_id} - Shop response:\n"
                f"{response_emoji.get(response, '')} {response_label.get(response, response)}"
            )
        except Exception as e:
            logger.error(f"Error saving announcement response: {e}")
            await query.edit_message_text("Error occurred. Please try again.")
        finally:
            db.close()

    async def _handle_cancel(self, update, context):
        context.user_data.pop('reporting_task', None)
        context.user_data.pop('rejecting_task', None)
        await update.message.reply_text("\u274c \u1015\u101a\u103a\u1016\u103b\u1000\u103a\u1015\u103c\u102e\u1038\u104b")

    async def _notify_admin(self, message):
        """Send notification to admin's Telegram"""
        if not Config.ADMIN_TELEGRAM_BOT_TOKEN or not Config.ADMIN_TELEGRAM_CHAT_ID:
            return
        try:
            bot = Bot(token=Config.ADMIN_TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=Config.ADMIN_TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    async def load_all_shop_bots(self):
        """Load and start bots for all active shops from DB"""
        import sqlite3
        db = sqlite3.connect(Config.DATABASE_PATH)
        db.row_factory = sqlite3.Row
        try:
            shops = db.execute("SELECT * FROM shops WHERE is_active = 1").fetchall()
            for shop in shops:
                await self.register_shop_bot(shop['id'], shop['telegram_bot_token'], shop['telegram_chat_id'])
            logger.info(f"Loaded {len(shops)} shop bots")
        except Exception as e:
            logger.error(f"Error loading shop bots: {e}")
        finally:
            db.close()


# Global instance
shop_bot_manager = ShopBotManager()
