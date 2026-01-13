FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y netcat-openbsd gcc libpq-dev gettext

COPY . .

# Install python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

RUN chmod +x entrypoint.sh

ENV PYTHONPATH=/app

ENTRYPOINT ["/app/entrypoint.sh"]