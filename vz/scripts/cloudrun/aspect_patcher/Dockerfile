FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main script and the classification pipeline subfolder
COPY main.py .
COPY classify/ classify/

# Run the job when the container starts
CMD ["python", "main.py"]
