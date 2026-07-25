#!/bin/bash
# Start the RevisorPlus demo. Open http://127.0.0.1:8000/ in your browser.
cd "$(dirname "$0")"
source ../medrev-venv/bin/activate
echo "RevisorPlus demo -> http://127.0.0.1:8000/"
echo "Logins:  student@revisorplus.test / demo12345   |   tutor@revisorplus.test / demo12345"
python manage.py runserver 127.0.0.1:8000
