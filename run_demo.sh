#!/bin/bash
# Start the Med-revisor demo. Open http://127.0.0.1:8000/ in your browser.
cd "$(dirname "$0")"
source ../medrev-venv/bin/activate
echo "Med-revisor demo -> http://127.0.0.1:8000/"
echo "Logins:  student@medrevisor.test / demo12345   |   tutor@medrevisor.test / demo12345"
python manage.py runserver 127.0.0.1:8000
