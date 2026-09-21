ARG PYTHON_IMAGE=python:3.13-slim-bookworm
FROM ${PYTHON_IMAGE}
WORKDIR /app
RUN mkdir /state && chown 1000:1000 /state
COPY gateway.py /app/gateway.py
USER 1000:1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "/app/gateway.py"]
