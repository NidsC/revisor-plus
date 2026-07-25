It has been launched on Render, use the following link: https://medrevisor.onrender.com

You can create your own account as a student 
To log in as a Tutor - username: tutor@medrevisor.test, password: demo12345
As a Tutor, you can oversee studnet progress, assign HW and maange student progress.
To log in as an Admin - username: admin@medrevisor.test, password: admin12345
As an admin, you can manage the entire system, add new tutor accounts manage payments, data etc
AND as ammin you can add/remove questions from the set.

Underlying tech stack 
- Backend: Python 3.12 + Django 5.1
- Auth: django-allauth (email login, role-based: student/tutor/admin)
- Frontend: Django templates + Bootstrap 5 + Chart.js
- Database: SQLite (local) → PostgreSQL (production)
- Payments: Stripe (test-mode Checkout)
- Serving: Gunicorn + WhiteNoise (static files)
- Hosting: Render (web service + managed Postgres)
- Version control: Git / GitHub
