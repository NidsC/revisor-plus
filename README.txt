REVISORPLUS — PARENT DASHBOARD PATCH

WHAT IT DOES
------------
- Removes the "student practice | Parent summary" toggle from Dashboard.
- Keeps Dashboard student-focused.
- Moves your EXISTING Parent summary design to a separate page.
- Adds "Parent" to the main navbar beside "My target".
- Adds: /parent/
- Creates backups before changing anything.

HOW TO USE
----------
1. Extract this ZIP.
2. Drag all 3 files into:
   F:\revisor-plus-main\revisor-plus-main

3. Double-click:
   APPLY_PARENT_DASHBOARD.bat

Or run:
   python apply_parent_dashboard.py

Then:
   python main.py runserver

Open:
   http://127.0.0.1:8000/parent/

BACKUPS
-------
Original files are copied to:
   .parent-dashboard-backup\<timestamp>\
