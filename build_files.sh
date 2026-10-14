#!/bin/bash
python3 -m pip install -r requirements.txt || pip install -r requirements.txt
python3 manage.py collectstatic --noinput || python manage.py collectstatic --noinput

