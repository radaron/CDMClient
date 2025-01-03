VIRTUALENV = .venv
ACTIVATE = . $(VIRTUALENV)/bin/activate


.venv:
	python3.9 -m venv $(VIRTUALENV)
	$(ACTIVATE) && pip install --upgrade pip pip-tools

clean:
	rm -rf $(VIRTUALENV)

virtualenv: .venv

reqs: virtualenv
	$(ACTIVATE) && pip install .[dev]

format:
	$(ACTIVATE) && black cdm_client/

lint:
	@$(ACTIVATE) && pylint cdm_client/
	@$(ACTIVATE) && mypy --install-types cdm_client/

.PHONY: build
build:
	@$(ACTIVATE) && python -m build

publish:
	@$(ACTIVATE) && python -m twine upload --skip-existing dist/*