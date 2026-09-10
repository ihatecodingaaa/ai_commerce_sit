FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m -u 10001 webuser && chown -R webuser:webuser /app
USER webuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
