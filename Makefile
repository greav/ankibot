clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "build"  -exec rm -r {} +
	find . -type d -name "*.egg-info"  -exec rm -r {} +

export_requirements:
	uv export --frozen --no-dev --no-hashes --output-file=requirements.txt

run:
	uv run --env-file .env -m ankibot

build_image:
	docker build -t ankibot .

run_container:
	docker run -v ${PWD}/configs/:/opt/configs --env-file .env ankibot
