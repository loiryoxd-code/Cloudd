# Python Base Image
FROM python:3.10-slim

# System Dependencies (including Oracle client dependencies if required)
RUN apt-get update && apt-get install -y \
    gcc \
    libaio1 \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Workdir Configuration
WORKDIR /app

# Copy Requirements and Install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Application Source Code
COPY . .

# Environment Defaults
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose Django App Port
EXPOSE 8000

# Gunicorn WSGI runtime start
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "securedocs.wsgi:application"]
