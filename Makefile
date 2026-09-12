PROTO_SRC := $(shell find proto -name '*.proto')
# Generated protobuf modules are not committed; the stamp tracks whether they are up to date.
# Generated at the repo root (not under ankibot/) so cross-file imports between generated modules
# (e.g. "import ankiweb/common.proto") resolve as the top-level package name protoc always gives
# them ("ankiweb.common_pb2"), with no sys.path or mypy_path juggling needed.
PROTO_STAMP := ankiweb/.stamp

.PHONY: clean export_requirements compile_proto run test list_models build_image run_container

clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "build"  -exec rm -r {} +
	find . -type d -name "*.egg-info"  -exec rm -r {} +

export_requirements:
	uv export --frozen --no-dev --no-hashes --output-file=requirements.txt

$(PROTO_STAMP): $(PROTO_SRC)
	mkdir -p $(dir $(PROTO_STAMP))
	uv run python -m grpc_tools.protoc \
		--proto_path=proto \
		--python_out=. \
		--pyi_out=. \
		$(PROTO_SRC)
	@touch $@

compile_proto: $(PROTO_STAMP)

run: $(PROTO_STAMP)
	uv run --env-file .env -m ankibot

test: $(PROTO_STAMP)
	uv run pytest

# Models the configured OpenAI key can call, one id per line (see scripts/list_openai_models.py).
list_models: $(PROTO_STAMP)
	uv run --env-file .env python -m scripts.list_openai_models

build_image:
	docker build -t ankibot .

run_container:
	docker run -v ${PWD}/configs/:/opt/configs -v ${PWD}/data:/opt/data --env-file .env ankibot
