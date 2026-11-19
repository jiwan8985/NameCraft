FROM python:3.14-slim
ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend:/app/apps/api NAMECRAFT_VAR_DIR=/app/var
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY backend backend
COPY apps/api apps/api
COPY scripts scripts
COPY datasets datasets
EXPOSE 8000
# import-data: 마이그레이션 + 출처 동기화 + Unihan(datasets/raw 에 있을 때) + 성씨 시드. 원천 파일이 없으면 경고 후 계속.
CMD ["sh", "-c", "python scripts/tasks.py import-data || python scripts/tasks.py migrate; exec uvicorn namecraft_api.main:create_app --factory --host 0.0.0.0 --port 8000 --no-access-log"]
