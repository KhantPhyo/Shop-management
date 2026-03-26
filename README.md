# Shop Management System 🏪📦

A comprehensive full-stack solution for managing a network of shops. Features include automated task assignment via Telegram, photo-report compliance, fine calculation, and a real-time analytics dashboard.

## 🌟 Key Features
- **Telegram Integration**: Dynamic multi-bot controller for shop-level interactions.
- **Task Management**: Lifecycle tracking from pending to completed/verified.
- **Myanmar Localized**: Integrated MMK currency and Myanmar Unicode support.
- **Analytics Dashboard**: React-based visual reporting for admin oversight.
- **Automated Scheduling**: Recurring task registry for routine operations.

---

## 🛠 Prerequisites
Ensure you have the following installed:
1. **Python 3.10+**
2. **Node.js (v18+)** & **npm**
3. **SQLite** (usually pre-installed)

---

## 🚀 Installation Guide

### 🍎 macOS
1. **Clone the project**:
   ```bash
   git clone https://github.com/KhantPhyo/Shop-management.git
   cd Shop-management
   ```
2. **Setup Backend**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Setup Frontend**:
   ```bash
   cd frontend
   npm install
   ```

### 🪟 Windows
1. **Setup Backend**:
   - Open PowerShell or Command Prompt:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Setup Frontend**:
   ```bash
   cd frontend
   npm install
   ```

### 🐧 Linux (Ubuntu/Debian)
1. **Setup Backend**:
   ```bash
   sudo apt update && sudo apt install python3-venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Setup Frontend**:
   ```bash
   cd frontend
   npm install
   ```

---

## ⚙️ Configuration
1. Create a `.env` file in the root directory (base on `config.py` structure).
2. Add your `ADMIN_TELEGRAM_BOT_TOKEN` and `JWT_SECRET`.
3. Configure your shops and their respective bot tokens via the dashboard.

---

## 🏃 Running the System
You need to run both the API and the Dashboard:

**Start Backend (API & Bots):**
```bash
# From root
source venv/bin/activate
python app.py
```

**Start Frontend (Dashboard):**
```bash
# From frontend folder
npm run dev
```

---

## 📂 Project Structure
- `tg_bots/`: Telegram engine for admin and shop interactions.
- `routes/`: Flask API endpoints.
- `frontend/`: React + Vite source code.
- `scheduler/`: Background task automation.

## 📄 License
MIT
