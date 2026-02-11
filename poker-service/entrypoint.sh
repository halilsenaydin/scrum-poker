#!/bin/sh
set -e  # Stop when getting error

if [ -f "/app/.config" ]; then
    . /app/.config
else
    echo "Not Found Config File! Using Default Settings..."

    PROJECT_NAME="microservice"
fi

if [ ! -f "manage.py" ]; then
    django-admin startproject $PROJECT_NAME .
fi

python manage.py collectstatic --noinput

if [ "$DEBUG" = "True" ]; then
    python manage.py makemigrations
fi

python manage.py migrate --noinput

python manage.py compilemessages

exec daphne -b 0.0.0.0 -p 8000 poker_service.asgi:application
