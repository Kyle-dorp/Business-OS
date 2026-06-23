BUSINESS OS SCHEDULING WORKSPACE — COMMERCIAL UI UPGRADE

WHAT THIS UPGRADE ADDS
- A polished soft blue/purple manager workspace.
- Persistent page state: the app reopens to the last page used.
- A real Home page with week selection, labor goal, projected sales blocks,
  schedule generation, regeneration, publishing, versions, warnings, and editing.
- Persistent AI chat stored in SQLite instead of disappearing on refresh.
- A separate "Things to always keep in mind" memory that is included with
  every GPT request.
- Correct week labels and optional schedule-version context in AI chat.
- Auto-growing AI composer.
- Position alias normalization (sandwiches -> Sandwich, dishwasher -> Dish,
  cashier -> Register). Missing positions are proposed as separate actions.
- Manager/Employee username-and-password login.
- Role-based permissions enforced by the backend.
- Employee schedule view, availability view, day-off requests, and availability
  change requests.
- Manager notification inbox with approve/deny actions.
- Account settings, username/password changes, logout, team account creation,
  and enable/disable controls.
- Existing database and existing assistant text are preserved. Old chat rows are
  adopted into the first manager account's assistant thread.

INSTALL
1. Stop backend and frontend with Ctrl+C.
2. Extract this ZIP into D:\Projects\scheduling-assistant and replace files.
3. In the backend terminal:
      cd D:\Projects\scheduling-assistant
      .\.venv\Scripts\Activate.ps1
      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
      .\install-commercial-upgrade.ps1
      python -m uvicorn backend.app.main:app --reload
4. In a second VS Code terminal:
      cd D:\Projects\scheduling-assistant\frontend
      npm run dev
5. Hard refresh the browser with Ctrl+Shift+R.
6. On first load, create the first Manager username and password.

IMPORTANT
- Do NOT delete schedule_assistant.db.
- The installer makes a timestamped database backup.
- Keep .env private. It contains the OpenAI key and login signing secret.
- Firebase is not required for this local build. Cloud sync and multi-device
  deployment should be connected after the local workflow is accepted.
