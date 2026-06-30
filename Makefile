VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PLAYWRIGHT = $(VENV)/bin/playwright

.PHONY: run clean

run: $(PLAYWRIGHT)
	$(PYTHON) yandex_parser2026.py

$(PLAYWRIGHT): $(VENV)/bin/activate
	$(PIP) install playwright pandas openpyxl beautifulsoup4 lxml colorama
	$(PLAYWRIGHT) install chromium

$(VENV)/bin/activate:
	python3 -m venv $(VENV)

clean:
	rm -rf $(VENV)
