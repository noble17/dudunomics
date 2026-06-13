FROM python:3.12-slim

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only backend source code
COPY api/ ./api/
COPY core/ ./core/

# Initialize data directory
RUN mkdir -p data

EXPOSE 8888

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8888"]
