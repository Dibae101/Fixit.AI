FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy project
COPY . .

# Expose port
EXPOSE 8000

# Create entrypoint script
RUN echo '#!/bin/bash\n\
python manage.py migrate\n\
python manage.py collectstatic --noinput\n\
exec "$@"\n' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Set entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "fixit_ai.wsgi:application", "--bind", "0.0.0.0:8000"]