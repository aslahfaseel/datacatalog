# Dockerfile.template
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the template creator script
COPY create_template.py .

# Explicitly run the template script
CMD ["python", "create_template.py"]