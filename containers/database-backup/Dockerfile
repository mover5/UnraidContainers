FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backup.py .
COPY backup/ backup/

VOLUME /backups

EXPOSE 8008

ENTRYPOINT ["python", "backup.py"]
