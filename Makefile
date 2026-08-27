PROTO_SRC := $(shell find proto -name '*.proto')
# Generated protobuf modules are not committed; the stamp tracks whether they are up to date.
PROTO_STAMP := ankibot/infra/anki/pb/.stamp

.PHONY: clean export_requirements compile_proto run test build_image run_container

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
		--python_out=ankibot/infra/anki/pb \
		--pyi_out=ankibot/infra/anki/pb \
		$(PROTO_SRC)
	@touch $@

compile_proto: $(PROTO_STAMP)

run: $(PROTO_STAMP)
	uv run --env-file .env -m ankibot

test: $(PROTO_STAMP)
	uv run pytest

build_image:
	docker build -t ankibot .

run_container:
	docker run -v ${PWD}/configs/:/opt/configs --env-file .env ankibot
