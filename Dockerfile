FROM python:3.13-slim AS proto

WORKDIR /build

RUN pip install --no-cache-dir grpcio-tools==1.82.1

COPY proto proto

RUN mkdir -p out && python -m grpc_tools.protoc \
        --proto_path=proto \
        --python_out=out \
        --pyi_out=out \
        $(find proto -name '*.proto')


FROM python:3.13-slim

WORKDIR /opt

RUN python -m venv /opt/venv

# Setting correct paths for packages (venv activation):
ENV PATH="/opt/venv/bin:$PATH"

ENV PYTHONUNBUFFERED=1

ENV CONFIG_PATH=/opt/configs/config.yaml

COPY requirements.txt .

RUN pip install --no-cache-dir --no-deps -r requirements.txt

COPY ankibot ankibot

# Sibling to ankibot/, not nested under it — see the PROTO_STAMP comment in the Makefile for why.
COPY --from=proto /build/out/ankiweb ankiweb

CMD ["python", "-m", "ankibot"]
