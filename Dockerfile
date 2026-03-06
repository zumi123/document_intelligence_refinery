# Document Intelligence Refinery — TRP1 Week 3
FROM python:3.11-slim

WORKDIR /app

# Install system deps for PDF handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpoppler-cpp-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/
COPY rubric/ rubric/
COPY scripts/ scripts/

RUN pip install --no-cache-dir -e .

# Default: run interim artifacts (override with CMD)
CMD ["python", "scripts/run_interim_artifacts.py"]
