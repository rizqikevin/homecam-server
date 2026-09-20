FROM python:3.11-slim

# System dependencies for OpenCV, video capture, and model download
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    v4l-utils \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bundled model and verify SHA256 (or download fallback if missing from context)
ARG POSE_MODEL_URL=https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
ARG POSE_MODEL_SHA256=59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a
COPY models/ /app/models/
RUN if [ ! -f /app/models/pose_landmarker_lite.task ]; then \
        curl -fSL -o /app/models/pose_landmarker_lite.task "${POSE_MODEL_URL}"; \
    fi \
    && echo "${POSE_MODEL_SHA256}  /app/models/pose_landmarker_lite.task" | sha256sum -c -

# Copy application
COPY app/ ./app/

# Create recordings directory
RUN mkdir -p /recordings

# Runtime environment
ENV POSE_MODEL_PATH=/app/models/pose_landmarker_lite.task
ENV HUMAN_DETECTION_INTERVAL_SECONDS=0.5

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
