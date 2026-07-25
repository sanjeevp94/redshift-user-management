.PHONY: help setup test lint plan apply

ENV ?= dev
TARGET ?=

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  setup    Install dependencies (uv, prek) and sync project."
	@echo "  test     Run the pytest suite."
	@echo "  lint     Run pre-commit checks using prek."
	@echo "  plan     Run the declarative RUM plan. Use ENV=<env> and TARGET=<host> to customize."
	@echo "  apply    Apply the declarative RUM changes. Use ENV=<env> and TARGET=<host> to customize."

setup:
	@echo "Setting up the environment..."
	@curl -LsSf https://astral.sh/uv/install.sh | sh
	@uv sync
	@uv tool install prek
	@uv pip install -e ".[dev]"

test:
	@echo "Running tests..."
	@uv run pytest tests/

lint:
	@echo "Running linting and formatting hooks..."
	@uv tool run prek run --all-files

plan:
	@echo "Running RUM plan for environment: $(ENV)"
	@if [ -n "$(TARGET)" ]; then \
		uv run rum plan --config=deploy/$(ENV)/config.yaml --target=$(TARGET); \
	else \
		uv run rum plan --config=deploy/$(ENV)/config.yaml; \
	fi

apply:
	@echo "Running RUM apply for environment: $(ENV)"
	@if [ -n "$(TARGET)" ]; then \
		uv run rum apply --config=deploy/$(ENV)/config.yaml --target=$(TARGET); \
	else \
		uv run rum apply --config=deploy/$(ENV)/config.yaml; \
	fi
