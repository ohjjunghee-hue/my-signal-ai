FROM python:3.12-slim
WORKDIR /app
COPY server.py index.html ./
ENV PYTHONUNBUFFERED=1 PORT=8765 DATA_DIR=/data
EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=4)" || exit 1
CMD ["python","server.py"]
