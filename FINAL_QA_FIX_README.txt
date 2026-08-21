FINAL QA FIX

This overlay is based on the commercial workspace upgrade and fixes:
- Projected Crew and Operations tabs crashing because CRUD/save handlers were missing.
- Home forecast block Save button overflowing its card.
- Team login form being autofilled with the current manager credentials.
- Blank account-type/profile placeholders for new logins.
- Notifications hover label and unread-count badge.
- Delete confirmation appearing repeatedly; destructive actions now confirm once per browser session.
- Responsive layout for sales blocks and manager action buttons.

INSTALL
1. Stop backend and frontend with Ctrl+C.
2. Copy everything from this ZIP into D:\Projects\scheduling-assistant and replace files.
3. Do NOT delete schedule_assistant.db or .env.
4. Backend:
   cd D:\Projects\scheduling-assistant
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m uvicorn backend.app.main:app --reload
5. Frontend in a second VS Code terminal:
   cd D:\Projects\scheduling-assistant\frontend
   npm run dev
6. Hard refresh with Ctrl+Shift+R.
