"""Print the models the configured OpenAI key can reach, one id per line.

Reads the same config the bot does (``CONFIG_PATH``), so the key and ``base_url`` are the ones
the bot would use. Run from the repository root, where ``ankibot`` resolves as a package:

    make list_models
    uv run --env-file .env python -m scripts.list_openai_models

The listing says which models the key may call, not what they can do: every id under
``model_catalog`` in ``configs/config.yaml`` must be in this list, and must also support
json_schema structured outputs and image input — check those against the model's documentation,
not this list.
"""

import asyncio
import os
import sys

from ankibot.bootstrap.config import load_config
from ankibot.infra.llm.openai_client import build_openai_client

CONFIG_PATH_ENV = "CONFIG_PATH"


async def main() -> None:
    config_path = os.environ.get(CONFIG_PATH_ENV)
    if config_path is None:
        print(f"'{CONFIG_PATH_ENV}' must point at the bot's YAML config", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)
    client = build_openai_client(config.openai_client)
    try:
        model_ids = sorted([model.id async for model in client.models.list()])
    finally:
        await client.close()

    for model_id in model_ids:
        print(model_id)
    print(f"{len(model_ids)} models at {config.openai_client.base_url}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
