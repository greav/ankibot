FROM python:3.11-slim AS builder

WORKDIR /opt

RUN python -m venv /opt/venv

# Setting correct paths for packages (venv activation):
ENV PATH="/opt/venv/bin:$PATH"

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir --no-deps -r requirements.txt

COPY proto proto

COPY ankibot ankibot

RUN mkdir -p ankibot/proto_gen && python -m grpc_tools.protoc --python_out=ankibot/proto_gen/ --proto_path=proto/ proto/*.proto

CMD ["python", "-m", "ankibot"]
