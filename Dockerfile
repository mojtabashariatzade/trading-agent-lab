FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 team && useradd --uid 10001 --gid 10001 --create-home team \
    && mkdir -p /app /state && chown -R 10001:10001 /app /state
WORKDIR /app
# Controller image deliberately does NOT include or execute candidate trading code.
COPY --chown=10001:10001 agentops ./agentops
COPY --chown=10001:10001 planning ./planning
USER 10001:10001
VOLUME ["/state"]
CMD ["python", "-m", "agentops"]
