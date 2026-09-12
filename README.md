# ankibot

Telegram bot for creating ankig cards

## Prerequisites

Before you begin, ensure you have the following tools installed:

- [uv](https://github.com/astral-sh/uv) - Modern Python package management (required for development)
- [pre-commit](https://github.com/pre-commit/pre-commit) - A tool for managing and maintaining Git pre-commit hooks

## Getting Started

There are two ways to set up the project environment depending on your needs:

### Basic Usage (Running the Project)

If you only need to run the project without adding new dependencies:

1. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   ```

1. Activate the virtual environment:

   ```bash
   # On macOS/Linux
   source .venv/bin/activate
   ```

1. Install dependencies from requirements.txt:

   ```bash
   pip install -r requirements.txt
   ```

### Development Usage (Managing Dependencies)

If you plan to add or modify dependencies:

1. Set up the environment with uv (it will create the virtual environment if it doesn't exist):

   ```bash
   # Install all dependencies including dev dependencies
   uv sync

   # Install only main dependencies
   uv sync --no-dev
   ```

1. Activate the virtual environment:

   ```bash
   # On macOS/Linux
   source .venv/bin/activate
   ```

## Managing Dependencies

### Adding New Packages

When developing, you have two options to add new packages:

1. Using uv command:

   ```bash
   # Add to main dependencies
   uv add package_name

   # Add as development dependency
   uv add --dev package_name
   ```

1. Manually editing the `pyproject.toml` file:

   ```toml
   # In pyproject.toml
   [project]
   dependencies = [
       "package_name",
   ]
   ```

   After editing the file, run `uv sync` to install the added packages.

### Generating Requirements Files

Export main dependencies to requirements.txt:

```bash
make export_requirements
```

## Running the Application

To run the application locally:

```bash
make run
```

To check which OpenAI models the configured key can call (every id under `model_catalog` in `configs/config.yaml` must be one of them):

```bash
make list_models
```

### Running with Docker

Build a Docker image:

```bash
make build_image
```

Run the application in a Docker container:

```bash
make run_container
```

## Configuration

The application is configured using YAML files in the `configs/` directory managed by [OmegaConf](https://github.com/omry/omegaconf). The default configuration file is `./configs/config.yaml`.

To use a custom configuration file, set the `CONFIG_PATH` environment variable:

```bash
CONFIG_PATH=./configs/custom-config.yaml make run
```

### Configuration Structure

OmegaConf provides hierarchical configuration with support for merging configs, variable interpolation, and type checking. Example configuration:

```yaml
# config.yaml
database:
  host: localhost
  port: 5432
  username: ${oc.env:DB_USER,default_user}
  password: ${oc.env:DB_PASSWORD,default_password}
```

## Development Workflow

### Running Tests

```bash
pytest
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pre-commit install
```

Run pre-commit hooks manually:

```bash
pre-commit run --all-files
```
