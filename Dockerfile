FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system audio, OCR, and document rendering dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install CPU-only PyTorch first to prevent downloading 2GB+ of unnecessary NVIDIA/CUDA drivers
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source files
COPY backend ./backend

# Create required storage directories
RUN mkdir -p /app/backend/storage/uploads \
             /app/backend/storage/transcripts \
             /app/backend/storage/temp \
             /app/backend/storage/qdrant

EXPOSE 8000

# Set working directory to backend so relative app imports work seamlessly
WORKDIR /app/backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
