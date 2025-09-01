FROM python:3.11-slim AS builder

WORKDIR /opt

RUN python -m venv /opt/venv

# Setting correct paths for packages (venv activation):
ENV PATH="/opt/venv/bin:$PATH"

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir --no-deps -r requirements.txt

COPY ankibot ankibot

CMD ["python", "-m", "ankibot"]
