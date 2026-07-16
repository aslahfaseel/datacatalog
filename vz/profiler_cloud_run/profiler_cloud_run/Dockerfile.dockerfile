# Use an official lightweight Python runtime
FROM python:3.10-slim

ENV PYTHONUNBUFFERED True

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY profiler_cloud_run.py .

ENTRYPOINT ["python", "profiler_cloud_run.py"]