FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies (libgomp1 is required by LightGBM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first
COPY requirements.txt .

# Install CPU-only PyTorch first, then install the rest of requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app/ ./app

# Copy default model/data storage if exists
COPY storage/ ./storage

# Create storage directory and ensure correct permissions
RUN mkdir -p /workspace/storage

# Environment variables
ENV ENV=production
ENV PORT=8000

# Run FastAPI app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
