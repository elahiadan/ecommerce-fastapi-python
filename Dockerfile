FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
COPY ./alembic ./alembic

# DATABASE_URL (PostgreSQL) and JWT_SECRET_KEY must be provided at runtime
# (e.g. -e DATABASE_URL=... -e JWT_SECRET_KEY=...) — the app refuses to boot
# without them. On first start it runs the Alembic migrations automatically.
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]