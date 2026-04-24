FROM python:3.12-slim
# FROM nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY . .

# RUN apt-get update && apt-get install -y patchelf python3-pip
RUN pip install --no-cache-dir --upgrade pip setuptools && \
  pip install --no-cache-dir -r requirements.txt

WORKDIR /app/src

# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8000"]
