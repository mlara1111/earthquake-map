FROM python:3.14-slim

### Install system dependencies required by GeoDjango.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

### Install Python dependencies.
COPY pyproject.toml .
RUN pip install --no-cache-dir .

### Copy application source code.
COPY src ./src

WORKDIR /app/src

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]