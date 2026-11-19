FROM python:3.14-slim
ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend:/app/apps/api NAMECRAFT_VAR_DIR=/app/var
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY backend backend
COPY apps/api apps/api
COPY datasets datasets
EXPOSE 8000
CMD ["sh", "-c", "python -c 'from namecraft.config import get_settings; from namecraft.db import migrate; migrate.upgrade(get_settings().resolved_database_url)' && uvicorn namecraft_api.main:create_app --factory --host 0.0.0.0 --port 8000"]
