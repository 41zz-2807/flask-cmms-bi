FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium \
 && rm -rf /root/.cache/pip

COPY app.py db.py queries.py auth.py admin.py ./
COPY templates ./templates
COPY static ./static

EXPOSE 8088

CMD ["gunicorn", "--bind", "0.0.0.0:8088", "--workers", "2", "--threads", "4", "app:app"]