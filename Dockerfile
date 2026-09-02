# Render Docker — ffmpeg + tgcrypto (needs gcc) + Pyrogram MTProto
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "Manhwaflare.main"]
