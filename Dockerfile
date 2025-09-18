# Multi-stage Dockerfile for HTTPx Scanner
FROM python:3.12-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install httpx tool
RUN curl -s https://api.github.com/repos/projectdiscovery/httpx/releases/latest \
    | grep "browser_download_url.*linux_amd64.zip" \
    | cut -d '"' -f 4 \
    | xargs curl -L -o httpx.zip \
    && unzip httpx.zip \
    && mv httpx /usr/local/bin/ \
    && chmod +x /usr/local/bin/httpx \
    && rm httpx.zip

# Production stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy httpx binary from builder
COPY --from=builder /usr/local/bin/httpx /usr/local/bin/httpx

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY run.py .

# Create necessary directories
RUN mkdir -p data/results data/wordlists data/lists logs \
    && chown -R app:app /app

# Switch to app user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/healthz || exit 1

# Run the application
CMD ["python", "run.py"]