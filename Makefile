.PHONY: setup.py requirements.txt

DIST_BASENAME := $(shell poetry version | tr ' ' '-')

all: precheck

.PHONY: prechck
precheck:
	black . && \
	pre-commit run -a && \
	interrogate -c pyproject.toml

package: setup.py requirements.txt

setup.py:
	poetry build && \
	tar --strip-components=1 -xvf dist/$(DIST_BASENAME).tar.gz '*/setup.py'

requirements.txt:
	poetry export --without-hashes > requirements.txt

clean:
	rm -rf dist *.egg-info .pytest_cache
	rm -f requirements.txt setup.py
	rm -f poetry.lock
	find . -name '__pycache__' | xargs rm -rf
