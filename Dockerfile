FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN mkdir -p /app/data /app/assets

ENV TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
ENV DEFAULT_WATERMARK=@yourusername
ENV WATERMARK_PATH=/app/assets/watermark.png
ENV DATA_DIR=/app/data

CMD ["python", "bot.py"]
