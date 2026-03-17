import os
import asyncio
import threading
import logging
from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config
from database import init_app as init_db_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Ensure upload directory exists
    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)

    # Initialize database
    init_db_app(app)

    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.shop_routes import shop_bp
    from routes.task_routes import task_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.report_routes import report_bp
    from routes.announcement_routes import announcement_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(announcement_bp)

    # Serve React frontend
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')

    @app.route('/')
    @app.route('/<path:path>')
    def serve_frontend(path=''):
        if path and os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, 'index.html')

    return app


def start_telegram_bots():
    """Start all Telegram bots in a separate thread with its own event loop"""
    async def run_bots():
        from tg_bots.shop_bot_manager import shop_bot_manager
        from tg_bots.admin_bot import admin_bot

        try:
            await shop_bot_manager.load_all_shop_bots()
            logger.info("All shop bots loaded")
        except Exception as e:
            logger.error(f"Error loading shop bots: {e}")

        try:
            await admin_bot.setup()
            logger.info("Admin bot started")
        except Exception as e:
            logger.error(f"Error starting admin bot: {e}")

        # Keep the loop running
        while True:
            await asyncio.sleep(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    from tg_bots.shop_bot_manager import shop_bot_manager
    shop_bot_manager.set_loop(loop)

    try:
        loop.run_until_complete(run_bots())
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")


app = create_app()

if __name__ == '__main__':
    # Start Telegram bots in background thread
    bot_thread = threading.Thread(target=start_telegram_bots, daemon=True)
    bot_thread.start()
    logger.info("Telegram bots starting in background thread...")

    # Start scheduler
    try:
        from scheduler.scheduler_init import init_scheduler
        init_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")

    # Run Flask
    app.run(
        host='0.0.0.0',
        port=Config.FLASK_PORT,
        debug=False  # Don't use debug with threading
    )
