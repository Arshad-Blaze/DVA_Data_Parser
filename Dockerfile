FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"

COPY dav_tool/ dav_tool/

EXPOSE 8501

ENTRYPOINT ["python", "-m", "dav_tool"]
