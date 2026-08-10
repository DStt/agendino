# CUDA + cuDNN 9 runtime so faster-whisper/CTranslate2 can run on the GPU.
# The image also runs fine on CPU (the CUDA libs sit unused when no GPU is reserved),
# so the same image serves both the CPU-default and GPU-toggle compose modes.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# The CUDA base image ships no Python — install it (Ubuntu 22.04 provides 3.10).
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools && \
    python3 -m pip install --no-cache-dir -r requirements.txt

WORKDIR /app/src
