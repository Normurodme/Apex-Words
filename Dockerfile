# Apex Words — bitta servis: aiogram bot + aiohttp (Mini App + API)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# build/ nusxalanmaydi: puzzle'lar va lug'at oldindan generatsiya qilinib,
# data/ va web_app/data/ ichida repoda turadi. Serverda NLTK/wordfreq kerak emas.
COPY bot.py .
COPY web_app/ ./web_app/
COPY data/ ./data/

EXPOSE 8080

CMD ["python", "bot.py"]
