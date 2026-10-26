#!/usr/bin/env bash

python manage.py rqworker default emails &

gunicorn backend.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 1 --preload