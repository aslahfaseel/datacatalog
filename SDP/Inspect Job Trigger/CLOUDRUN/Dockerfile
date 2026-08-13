FROM python:3.11-slim

WORKDIR /app

# Force the container to use the proxy for all internet traffic
ENV HTTP_PROXY="http://proxy.ebiz.verizon.com:80/"
ENV HTTPS_PROXY="http://proxy.ebiz.verizon.com:80/"
ENV http_proxy="http://proxy.ebiz.verizon.com:80/"
ENV https_proxy="http://proxy.ebiz.verizon.com:80/"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY sdp-inspect-jobs.py .

CMD ["python", "sdp-inspect-jobs"]