FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing .pyc files & enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime dependencies
RUN pip install --no-cache-dir fastapi uvicorn jinja2 httpx

# Copy application files
COPY app.py .
COPY templates/ ./templates/

# Run as non-root user for security best practices
RUN useradd -u 1001 appuser && chown -R appuser:appuser /app
USER 1001

EXPOSE 8881

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8881", "--no-access-log"]