#!/bin/sh
# Container start: apply migrations, build any missing thumbnails, then serve with Gunicorn.
set -e
python manage.py migrate --noinput
python manage.py optimize_images
exec gunicorn artstock.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-3}" \
  --access-logfile - \
  --timeout 60
