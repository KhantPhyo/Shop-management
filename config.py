import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    JWT_SECRET = os.getenv('JWT_SECRET', 'dev-jwt-secret')
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    ADMIN_TELEGRAM_BOT_TOKEN = os.getenv('ADMIN_TELEGRAM_BOT_TOKEN', '')
    ADMIN_TELEGRAM_CHAT_ID = os.getenv('ADMIN_TELEGRAM_CHAT_ID', '')
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5050')
    UPLOAD_DIR = os.getenv('UPLOAD_DIR', './uploads')
    DATABASE_PATH = os.getenv('DATABASE_PATH', './database.db')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5050))
    REMINDER_INTERVAL_MINUTES = int(os.getenv('REMINDER_INTERVAL_MINUTES', 60))
    DEFAULT_FINE_AMOUNT_MMK = int(os.getenv('DEFAULT_FINE_AMOUNT_MMK', 500))
