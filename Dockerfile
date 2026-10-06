FROM python:3.10-slim

# Prevent Python from writing .pyc files, enable unbuffered logging, and restrict C++ thread pools
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV ONNXRUNTIME_NUM_THREADS=1

# Install system audio, OCR, and document rendering dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install CPU-only PyTorch first (if required by downstream dependencies) to prevent downloading heavy CUDA drivers
RUN pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend source files
COPY backend ./backend
COPY frontend ./frontend

# Create required storage directories
RUN mkdir -p /app/backend/storage/uploads \
             /app/backend/storage/transcripts \
             /app/backend/storage/temp \
             /app/backend/storage/qdrant

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
