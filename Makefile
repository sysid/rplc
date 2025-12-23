.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

# You can set these variables from the command line, and also from the environment for the first two.
SOURCEDIR     = source
BUILDDIR      = build
MAKE          = make
VERSION       = $(shell cat VERSION)

app_root = $(PROJ_DIR)
app_root ?= .
pkg_src =  src/rplc
tests_src = tests

.PHONY: all
all: clean build publish  ## Build and publish
	@echo "--------------------------------------------------------------------------------"
	@echo "-M- building and distributing"
	@echo "--------------------------------------------------------------------------------"


################################################################################
# Developing \
DEVELOP: ## ############################################################

################################################################################
# Testing \
TESTING:  ## ############################################################

.PHONY: test
test:   ## test
	RUN_ENV=test python -m pytest --cov-report=xml --cov-report term --cov=src/rplc tests

.PHONY: init
init:  ## init: remove test setup 'xxx'
	rm -vrf $(HOME)/dev/s/private/py-twlib/rplc/sysid/xxx

################################################################################
# Code Quality \
QUALITY: ## ############################################################

.PHONY: lint
lint:  ## check style with ruff
	ruff check $(pkg_src) $(tests_src)

.PHONY: lint-fix  ## autofix linter findings
lint-fix:  ## check style with ruff
	ruff check --fix $(pkg_src) $(tests_src)

.PHONY: static-analysis
static-analysis: lint-fix format ty  ## run all static code analysis (check/format/ty)

.PHONY: ty
ty:  ## check type hint annotations
	@uvx ty check $(pkg_src)

.PHONY: format
format:  ## Format code with ruff
	ruff format $(pkg_src) $(tests_src)

################################################################################
# Building, Deploying \
BUILDING:  ## ############################################################

.PHONY: build
build: clean  ## format and build
	@echo "building"
	python -m build

.PHONY: publish
publish:  ## publish
	@echo "upload to Pypi"
	twine upload --verbose dist/*

.PHONY: upload
upload:   ## twine upload
	@echo "upload"
	twine upload --verbose dist/*

.PHONY: install
install: uninstall  ## pipx install
	uv tool install -e .
	rplc --install-completion bash

.PHONY: uninstall
uninstall:  ## pipx uninstall
	-uv tool uninstall rplc

.PHONY: bump-major
bump-major:  check-github-token  ## bump-major, tag and push
	bump-my-version bump --commit --tag major
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: bump-minor
bump-minor:  check-github-token  ## bump-minor, tag and push
	bump-my-version bump --commit --tag minor
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: bump-patch
bump-patch:  check-github-token  ## bump-patch, tag and push
	bump-my-version bump --commit --tag patch
	git push
	git push --tags
	@$(MAKE) create-release

.PHONY: create-release
create-release: check-github-token  ## create a release on GitHub via the gh cli
	@if ! command -v gh &>/dev/null; then \
		echo "You do not have the GitHub CLI (gh) installed. Please create the release manually."; \
		exit 1; \
	else \
		echo "Creating GitHub release for v$(VERSION)"; \
		gh release create "v$(VERSION)" --generate-notes; \
	fi

.PHONY: check-github-token
check-github-token:  ## Check if GITHUB_TOKEN is set
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "GITHUB_TOKEN is not set. Please export your GitHub token before running this command."; \
		exit 1; \
	fi
	@echo "GITHUB_TOKEN is set"

################################################################################
# Clean \
CLEAN:  ## ############################################################

.PHONY: clean
clean: clean-build clean-pyc  ## remove all build, test, coverage and Python artifacts

.PHONY: clean-build
clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . \( -path ./env -o -path ./venv -o -path ./.env -o -path ./.venv \) -prune -o -name '*.egg-info' -exec rm -fr {} +
	find . \( -path ./env -o -path ./venv -o -path ./.env -o -path ./.venv \) -prune -o -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +


################################################################################
# Misc \
MISC:  ## ############################################################
define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z0-9_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("\033[36m%-20s\033[0m %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

.PHONY: help
help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)
