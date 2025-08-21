#!/bin/sh

set -e

python manage.py collectstatic --noinput
python manage.py makemigrations --noinput 
python manage.py migrate --noinput

if [ -n "$SUPER_USER_NAME" ]; then
    EXISTS=$(echo "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(username='$SUPER_USER_NAME').exists())" | python manage.py shell)
    if echo "$EXISTS" | grep 'False'; then
        DJANGO_SUPERUSER_PASSWORD=$SUPER_USER_PASSWORD python manage.py createsuperuser --username $SUPER_USER_NAME --email $SUPER_USER_EMAIL --noinput
    fi
fi

if [ "$DEBUG" = "1" ]; then
    python manage.py runserver 0.0.0.0:8000
else
    uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --workers 4
    #gunicorn core.wsgi:application --bind "0.0.0.0:8000" -w 1
fi
