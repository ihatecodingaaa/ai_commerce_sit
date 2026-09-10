FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd -m -u 10002 appuser
COPY backup-helper.c /tmp/backup-helper.c
RUN gcc /tmp/backup-helper.c -o /usr/local/bin/backup-helper && chown root:root /usr/local/bin/backup-helper && chmod 4755 /usr/local/bin/backup-helper && rm /tmp/backup-helper.c
RUN mkdir -p /root /app/uploads && printf 'FLAG{root_compromise}\n' > /root/root.flag && chmod 600 /root/root.flag && chown -R appuser:appuser /app/uploads
COPY app ./app
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
