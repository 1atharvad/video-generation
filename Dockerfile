FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    git ffmpeg \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install torch with CUDA first, then remaining deps
RUN pip3 install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu121

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Download models at build time so containers start instantly
RUN python3 -c "import sys; sys.path.insert(0, 'src'); from liveportrait.setup import setup_all; setup_all()"
