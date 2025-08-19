# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Install system dependencies for pyvips and other requirements
RUN apt-get update && apt-get install -y \
    libvips-dev \
    libvips-tools \
    gcc \
    g++ \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files213
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/

# Create static and cache directories
RUN mkdir -p static cache/grid

# Copy config example and create production config
COPY config.toml.example ./config.toml
RUN sed -i 's/HOST = "127.0.0.1"/HOST = "0.0.0.0"/' config.toml

# Set environment variables for production
ENV HOST=0.0.0.0
ENV PORT=3000

# Expose the application port
EXPOSE 3000/tcp

# Run the application with uv run to ensure dependencies are available
ENTRYPOINT ["uv", "run", "--", "python", "src/main.py"]