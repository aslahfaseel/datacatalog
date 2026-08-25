FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sdp-inspect-jobs.py .
CMD ["python", "sdp-inspect-jobs.py"]
