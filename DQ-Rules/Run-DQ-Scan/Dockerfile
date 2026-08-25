# Dockerfile.scanrunner
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the scan runner script
COPY run_scans.py .

# Explicitly run the scan runner script
CMD ["python", "run_scans.py"]