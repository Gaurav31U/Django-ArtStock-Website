FROM python:3.9-slim

WORKDIR /app

RUN pip install django
RUN pip install pillow

COPY . /app/

EXPOSE 8000

RUN python manage.py migrate


CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]