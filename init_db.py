from database import init_db
import os

if __name__ == "__main__":
    print("🚀 Initializing Shop Management Database...")
    init_db()
    
    if os.path.exists('database.db'):
        print("✅ Success! 'database.db' has been created with all required tables.")
        print("👤 Default Admin account created (see .env for credentials).")
    else:
        print("❌ Error: Database file was not created.")
