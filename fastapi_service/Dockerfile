FROM python:3.10-slim

WORKDIR /code

# Install system dependencies, including FFmpeg and ImageMagick for MoviePy/Pydub
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    ffmpeg \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick policy to allow PDF/video/image editing if needed by MoviePy
RUN sed -i 's/domain="coder" rights="none" pattern="PDF"/domain="coder" rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml || true

# Install python dependencies
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /code/

EXPOSE 8001
