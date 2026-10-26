#!/usr/bin/env bash

python manage.py rqworker default emails &

gunicorn core.wsgi:application --bind 0.0.0.0:$PORT