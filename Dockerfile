# 웹 서버(Flask) 이미지 — docker-compose.yml 의 web 서비스
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.py run.py ./
COPY app ./app
ENV PYTHONUNBUFFERED=1 APP_HOST=0.0.0.0
EXPOSE 5000
CMD ["python", "run.py"]
