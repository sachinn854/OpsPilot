FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2, fastembed, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend/ ./backend/

# Pre-download fastembed models so first request isn't slow
RUN python -c "from fastembed import TextEmbedding, SparseTextEmbedding; \
    TextEmbedding('BAAI/bge-small-en-v1.5'); \
    SparseTextEmbedding('Qdrant/bm25')" || true

EXPOSE 8000

# start.sh runs migrations then starts uvicorn
COPY backend/start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
