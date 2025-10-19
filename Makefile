reqs:
	uv sync --dev

format:
	uv run ruff format cdm_client/
	uv run ruff check --select I --fix cdm_client/

lint:
	uv run ruff check cdm_client/
	uv run mypy cdm_client/

reqs-ci:
	uv sync --dev --locked

check-format:
	uv run ruff format --check cdm_client/
	uv run ruff check --select I cdm_client/

.PHONY: build
build:
	uv build

publish:
	uv publish

bump:
	uv version --bump $(filter-out $@,$(MAKECMDGOALS))
