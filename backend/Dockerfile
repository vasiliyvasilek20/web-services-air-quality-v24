FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/main.py .
COPY web-service/aqi.py .
EXPOSE 8000
CMD ["python", "main.py"]
