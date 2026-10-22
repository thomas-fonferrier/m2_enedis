# Application Streamlit GreenTech — DPE & consommation
# Build : docker build -t greentech-dpe .
# Run   : docker run -p 8501:8501 greentech-dpe   →  http://localhost:8501
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Navigateur utilisé par kaleido pour l'export PNG des graphiques
    BROWSER_PATH=/usr/bin/chromium

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances d'abord : couche mise en cache tant que les requirements ne changent pas
COPY models/requirements.txt models/requirements.txt
COPY app/requirements.txt app/requirements.txt
RUN pip install -r app/requirements.txt

COPY .streamlit .streamlit
COPY app app
COPY models models
COPY data/raw data/raw

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8501}/_stcore/health')"

# $PORT est fourni par Render / Heroku ; 8501 en local
CMD ["sh", "-c", "streamlit run app/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
