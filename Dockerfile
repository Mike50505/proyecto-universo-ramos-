FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput
RUN DJANGO_DEBUG=1 python manage.py check
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn universo.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
