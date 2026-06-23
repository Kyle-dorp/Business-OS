Set-Location "D:\Projects\scheduling-assistant"
& ".\.venv\Scripts\Activate.ps1"
python -m uvicorn backend.app.main:app --reload
