# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    gcc \
    ca-certificates \
    ffmpeg \
    fontconfig \
    imagemagick \
    libbz2-1.0 \
    libc6  \
    libcairo2-dev \
    libcom-err2 \ 
    libcrypt1 \
    libdb5.3 \
    libexpat1 \
    libffi8 \
    libgdbm6 \
    libgssapi-krb5-2 \
    libjpeg-dev \
    libk5crypto3 \ 
    libkeyutils1 \
    libkrb5-3 \
    libkrb5support0 \
    liblzma5 \
    libncursesw6 \
    libnsl2 \
    libpango1.0-dev \
    libreadline8 \
    libsqlite3-0 \
    libssl3 \
    libtinfo6 \
    libtirpc3 \
    libuuid1 \
    make \
    netbase \
    tzdata \
    vim \
    zlib1g \
    zlib1g-dev \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Command to run on container start
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
