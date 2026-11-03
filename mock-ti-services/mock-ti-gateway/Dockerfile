FROM docker.io/library/python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx "pyjwt[crypto]" cryptography
COPY gateway.py .
EXPOSE 8082
CMD ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "8082"]
