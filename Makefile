# ==============================================================================
# CONFIG
# ==============================================================================

# Directories
BUILD_DIR        := build
RDF_DIR          := $(BUILD_DIR)/rdf
PYTHON_DIR       := src/python
R_DIR            := src/r

# Tools and binaries
ROBOT_VERSION    := v1.9.5
PYTHON           ?= $(shell command -v python3 || command -v python)
VENV             ?= venv
VENV_BIN         := $(VENV)/bin
VENV_PYTHON      := $(VENV_BIN)/python
VENV_PIP         := $(VENV_BIN)/pip
PYSHACL          := $(VENV_BIN)/pyshacl
PYTEST           := $(VENV_BIN)/pytest -p no:cacheprovider # suppress cache
ROBOT            := java -jar $(VENV_BIN)/robot.jar
RSCRIPT          ?= Rscript
R_REQUIREMENTS   := $(wildcard $(R_DIR)/requirements.txt)
R_STAMP          := $(if $(R_REQUIREMENTS),$(VENV)/.r-packages-installed.stamp)
PLANTUML_VERSION   := 1.2024.3
PLANTUML_JAR       := $(VENV_BIN)/plantuml.jar
VENV_JAVA_DIR      := $(VENV)/java17
JAVA17             := $(VENV_JAVA_DIR)/jdk-17.0.2/bin/java

# Inputs
ONTO             := $(wildcard src/rdf/ontology/*.owl.ttl)
DATA             := $(wildcard src/rdf/data/*.ttl)
SHAPES           := src/rdf/shapes/model.shacl.ttl
METADATA         := src/rdf/metadata.ttl
PREFIXES         := src/rdf/prefixes.ttl
QUERIES          := $(sort $(wildcard src/sparql/processing/*.rq))
PIPELINE_SCRIPTS := $(sort $(wildcard src/python/pipeline/*.py))

# Intermediate & Output Files
FETCHED_DATA     := $(RDF_DIR)/00-integrated.ttl
MERGED_DATA      := $(RDF_DIR)/01-merged.ttl
INFERRED_DATA    := $(RDF_DIR)/02-inferred.ttl
PROCESSED_DATA   := $(RDF_DIR)/03-processed.ttl
SHACL_REPORT     := $(RDF_DIR)/04-shacl-report.ttl
DOCS_DIR         := docs
PUML_SRC         := $(wildcard $(DOCS_DIR)/*/assets/puml/*.puml)
PUML_SVG         := $(subst /puml/,/img/,$(PUML_SRC:.puml=.svg))

# Logs
LOG_DIR          := $(BUILD_DIR)/log
MERGE_LOG        := $(LOG_DIR)/01-merge.log
INFER_LOG        := $(LOG_DIR)/02-infer.log
QUERY_LOG        := $(LOG_DIR)/03-query.log
SHACL_LOG        := $(LOG_DIR)/04-shacl.log
QUARTO_LOG       := $(LOG_DIR)/05-quarto.log

# Colors for logging
RED              := \033[0;31m
GREY             := \033[0;90m
BOLD             := \033[1;37m
NC               := \033[0m

.PHONY: all help robot test docs clean check-python venv install-dependencies install-r-packages setup build delete publish stamp-metadata generate-shacl-docs generate-glossary-docs

# Default target
all: test docs ## Run the tests and build the documentation (default)

# ==============================================================================
# HELP
# ==============================================================================

# Lists every target that carries a "## description" after its rule line.
help: ## Show this help
	@printf "$(BOLD)Usage:$(NC) make <target>\n\n$(BOLD)Targets:$(NC)\n"
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "} {printf "  $(BOLD)%-24s$(NC) %s\n", $$1, $$2}'
	@printf "\nThe default target is $(BOLD)all$(NC). Publishing requires USER, PASSWORD, GRAPH and ENDPOINT in .env.\n"

# ==============================================================================
# SETUP
# ==============================================================================

# 1. Check python interpreter
check-python:
	@command -v $(PYTHON) >/dev/null 2>&1 || \
		(printf "$(RED)ERROR: Python interpreter not found.$(NC)\n"; exit 1)

# 2. Set up virtual environment
$(VENV_PYTHON):
	@command -v $(PYTHON) >/dev/null 2>&1 || \
		(printf "$(RED)ERROR: Python interpreter not found.$(NC)\n"; exit 1)
	@printf "$(BOLD)[*] Setting up Python virtual environment...$(NC)\n"
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@printf "$(GREY)"; $(VENV_PYTHON) -m pip install --upgrade pip || { printf "$(NC)"; exit 1; }; printf "$(NC)"

venv: $(VENV_PYTHON)

# 3. Install python dependencies
$(VENV)/.requirements-installed.stamp: $(PYTHON_DIR)/requirements.txt | $(VENV_PYTHON)
	@printf "$(BOLD)[*] Installing Python dependencies...$(NC)\n"
	@printf "$(GREY)"; $(VENV_PIP) install -q -r $(PYTHON_DIR)/requirements.txt || { printf "$(NC)"; exit 1; }; printf "$(NC)"
	@touch $@

install-dependencies: $(VENV)/.requirements-installed.stamp

# 4. Install R packages (the stamp is only defined if src/r/requirements.txt exists)
$(VENV)/.r-packages-installed.stamp: $(R_REQUIREMENTS) $(R_DIR)/utils/install_packages.R | $(VENV_PYTHON)
	@command -v $(RSCRIPT) >/dev/null 2>&1 || \
		(printf "$(RED)ERROR: R not found (Rscript). Install R or delete $(R_DIR)/ if the documentation does not use R.$(NC)\n"; exit 1)
	@printf "$(BOLD)[*] Installing R packages...$(NC)\n"
	@printf "$(GREY)"; $(RSCRIPT) $(R_DIR)/utils/install_packages.R $(R_REQUIREMENTS) || { printf "$(NC)"; exit 1; }; printf "$(NC)"
	@touch $@

install-r-packages: $(R_STAMP)

# 5. Install robot
$(VENV_BIN)/robot.jar: | $(VENV_PYTHON)
	@printf "$(BOLD)[*] Downloading ROBOT ontology tool...$(NC)\n"
	@printf "$(GREY)"; curl -sL https://github.com/ontodev/robot/releases/download/$(ROBOT_VERSION)/robot.jar -o $(VENV_BIN)/robot.jar || { printf "$(NC)"; exit 1; }; printf "$(NC)"

robot: $(VENV_BIN)/robot.jar

# 6. Install PlantUML (for root-free pure Java rendering)
$(PLANTUML_JAR): | $(VENV_PYTHON)
	@printf "$(BOLD)[*] Downloading PlantUML...$(NC)\n"
	@printf "$(GREY)"; curl -sLf https://github.com/plantuml/plantuml/releases/download/v$(PLANTUML_VERSION)/plantuml-$(PLANTUML_VERSION).jar -o $(PLANTUML_JAR) || \
	(printf "$(NC)\n$(RED)ERROR: Download failed. Check the version/URL.$(NC)\n" && rm -f $(PLANTUML_JAR) && exit 1); printf "$(NC)"

# 7. Install local Java 17 for PlantUML
$(JAVA17): | $(VENV)
	@printf "$(BOLD)[*] Downloading portable Java 17...$(NC)\n"
	@printf "$(GREY)"; mkdir -p $(VENV_JAVA_DIR); \
	curl -sL https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_linux-x64_bin.tar.gz | tar -xz -C $(VENV_JAVA_DIR) || { printf "$(NC)"; exit 1; }; printf "$(NC)"

# 8. Full setup
setup: install-dependencies install-r-packages robot $(PLANTUML_JAR) $(JAVA17) ## Create the virtual environment, install Python and R dependencies, ROBOT, PlantUML and Java 17
	@printf "$(BOLD)[*] Setup complete.$(NC)\n"

# ==============================================================================
# RDF DATA INTEGRATION, REASONING AND POST-PROCESSING
# ==============================================================================

# 1. Set up directories
$(RDF_DIR) $(LOG_DIR) $(BUILD_DIR):
	@mkdir -p $@

# 2. Fetch, Query, and Transform source data sequentially
$(FETCHED_DATA): $(PIPELINE_SCRIPTS) $(PREFIXES) src/python/utils/turtle_serializer.py | $(RDF_DIR) $(LOG_DIR) $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Running data integration pipelines...$(NC)\n"
	@printf "$(GREY)"; \
	if [ -n "$(PIPELINE_SCRIPTS)" ]; then \
		for script in $(PIPELINE_SCRIPTS); do \
			echo "Executing $$script..."; \
			$(VENV_PYTHON) "$$script" --output $(FETCHED_DATA) || { printf "$(NC)"; exit 1; }; \
		done; \
	else \
		echo "No pipeline scripts found. Creating empty data file."; \
		touch $(FETCHED_DATA); \
	fi; \
	$(VENV_PYTHON) src/python/utils/turtle_serializer.py -i $(FETCHED_DATA) -p $(PREFIXES) -o $(FETCHED_DATA) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

# 3. Check that all turtle files are syntactically valid
$(LOG_DIR)/syntax-check.stamp: $(DATA) $(ONTO) $(SHAPES) $(METADATA) $(PREFIXES) $(FETCHED_DATA) tests/test_syntax.py | $(LOG_DIR) $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Checking Turtle syntax...$(NC)\n"
	@printf "$(GREY)"; \
	$(PYTEST) tests/test_syntax.py -q > /dev/null 2>&1 || { printf "$(NC)\n$(RED)[ERROR] Syntax check failed:$(NC)\n"; $(PYTEST) tests/test_syntax.py -v; exit 1; }; \
	printf "$(NC)"
	@touch $@

# 4. Merge ontology, shapes, static data, fetched data, and prefixes
$(MERGED_DATA): $(ONTO) $(SHAPES) $(METADATA) $(DATA) $(FETCHED_DATA) $(PREFIXES) $(LOG_DIR)/syntax-check.stamp src/python/utils/turtle_serializer.py | $(LOG_DIR) $(VENV_BIN)/robot.jar $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Merging ontology, shapes and data...$(NC)\n"
	@printf "$(GREY)"; \
	$(ROBOT) merge \
		$(foreach o,$(ONTO),--input $(o)) \
		--input $(SHAPES) \
		--input $(METADATA) \
		$(foreach d,$(DATA),--input $(d)) \
		--input $(FETCHED_DATA) \
		--input $(PREFIXES) \
		--output $(MERGED_DATA) > $(MERGE_LOG) 2>&1 || { printf "$(NC)\n$(RED)ERROR: ROBOT merge failed. See log below:$(NC)\n$(GREY)"; cat $(MERGE_LOG); printf "$(NC)\n"; exit 1; }; \
	$(VENV_PYTHON) src/python/utils/turtle_serializer.py -i $(MERGED_DATA) -p $(PREFIXES) -o $(MERGED_DATA) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

# 5. Inference using HermiT
$(INFERRED_DATA): $(MERGED_DATA) $(PREFIXES) src/python/utils/turtle_serializer.py | $(LOG_DIR) $(VENV_BIN)/robot.jar $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Running logical inference (HermiT)...$(NC)\n"
	@printf "$(GREY)"; \
	$(ROBOT) reason \
		--input $(MERGED_DATA) \
		--reasoner HermiT \
		--axiom-generators "SubClass" \
		--include-indirect true \
		--output $(INFERRED_DATA) > $(INFER_LOG) 2>&1 || { printf "$(NC)\n$(RED)ERROR: ROBOT reason failed. See log below:$(NC)\n$(GREY)"; cat $(INFER_LOG); printf "$(NC)\n"; exit 1; }; \
	$(VENV_PYTHON) src/python/utils/turtle_serializer.py -i $(INFERRED_DATA) -p $(PREFIXES) -o $(INFERRED_DATA) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

# 6. Model-driven processing via SPARQL
$(PROCESSED_DATA): $(INFERRED_DATA) $(QUERIES) $(PREFIXES) src/python/utils/turtle_serializer.py | $(LOG_DIR) $(VENV_BIN)/robot.jar $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Applying SPARQL updates...$(NC)\n"
	@printf "$(GREY)"; \
	if [ -z "$(QUERIES)" ]; then \
		cp $(INFERRED_DATA) $(PROCESSED_DATA); \
	else \
		$(ROBOT) query \
			--input $(INFERRED_DATA) \
			$(foreach q,$(QUERIES),--update $(q)) \
			convert --output $(PROCESSED_DATA) > $(QUERY_LOG) 2>&1 || { printf "$(NC)\n$(RED)ERROR: ROBOT query failed. See log below:$(NC)\n$(GREY)"; cat $(QUERY_LOG); printf "$(NC)\n"; exit 1; }; \
	fi; \
	$(VENV_PYTHON) src/python/utils/turtle_serializer.py -i $(PROCESSED_DATA) -p $(PREFIXES) -o $(PROCESSED_DATA) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

# 7. Trigger the whole graph build process
build: $(PROCESSED_DATA) ## Build the graph: integration, reasoning, SPARQL processing

# ==============================================================================
# BUILD DOCUMENTATION
# ==============================================================================

# Hand-drawn PlantUML diagrams of the documentation, per language:
# docs/<lang>/assets/puml/<name>.puml -> docs/<lang>/assets/img/<name>.svg
define PUML_RULE
$(subst /puml/,/img/,$(1:.puml=.svg)): $(1) | $(PLANTUML_JAR) $(JAVA17)
	@printf "$(BOLD)[*] Rendering $(notdir $(1)) with PlantUML...$(NC)\n"
	@mkdir -p $$(dir $$@)
	@printf "$(GREY)"; \
	$(JAVA17) -jar $(PLANTUML_JAR) -tsvg $$< -o $$(abspath $$(dir $$@)) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"
endef
$(foreach puml,$(PUML_SRC),$(eval $(call PUML_RULE,$(puml))))

generate-shacl-docs: $(SHAPES) $(PREFIXES) $(PROCESSED_DATA) $(DOCS_DIR)/_ech.yml src/python/utils/generate_shacl_docs.py | $(VENV)/.requirements-installed.stamp ## Generate the data model pages from the SHACL shapes
	@printf "$(BOLD)[*] Generating SHACL documentation...$(NC)\n"
	@printf "$(GREY)"; \
	$(VENV_PYTHON) src/python/utils/generate_shacl_docs.py -i $(SHAPES) -d $(DOCS_DIR) -p $(PREFIXES) -g $(PROCESSED_DATA) -c $(DOCS_DIR)/_ech.yml || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

generate-glossary-docs: src/rdf/data/glossary.skos.ttl $(PREFIXES) src/python/utils/generate_glossary_docs.py | $(VENV)/.requirements-installed.stamp ## Generate the glossary pages from the SKOS glossary
	@printf "$(BOLD)[*] Generating glossary documentation...$(NC)\n"
	@printf "$(GREY)"; \
	$(VENV_PYTHON) src/python/utils/generate_glossary_docs.py -i src/rdf/data/glossary.skos.ttl -d $(DOCS_DIR) -p $(PREFIXES) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

docs: $(SHACL_REPORT) generate-shacl-docs generate-glossary-docs $(PUML_SVG) $(R_STAMP) ## Generate the data model and glossary pages, render the diagrams and the documentation (website, PDF)
	@printf "$(BOLD)[*] Rendering documentation with Quarto...$(NC)\n"
	@printf "$(GREY)"; \
	quarto render docs > $(QUARTO_LOG) 2>&1 || { printf "$(NC)\n$(RED)ERROR: Quarto rendering failed. See log below:$(NC)\n$(GREY)"; cat $(QUARTO_LOG); printf "$(NC)\n"; exit 1; }; \
	printf "$(NC)"

# ==============================================================================
# TESTS
# ==============================================================================

# 1. SHACL validation
$(SHACL_REPORT): $(PROCESSED_DATA) $(SHAPES) | $(LOG_DIR) $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Running SHACL engine...$(NC)\n"
	@printf "$(GREY)"; \
	$(PYSHACL) -s $(SHAPES)  -a -f turtle -o $(SHACL_REPORT) $(PROCESSED_DATA) > $(SHACL_LOG) 2>&1 || true; \
	printf "$(NC)"

# 2. Run pytest (relies on written SHACL reports for all shape-related tests)
test: build $(SHACL_REPORT) | $(VENV)/.requirements-installed.stamp ## Build the graph, validate it with SHACL and run the test suite
	@printf "$(BOLD)[*] Running final test suite...$(NC)\n"
	@$(PYTEST) tests/ -v

# ==============================================================================
# PUBLICATION
# ==============================================================================

# 1. Import environment variables natively into Make
-include .env
export

# 2. Delete the existing data from LINDAS
delete: ## Delete the published graph from LINDAS (needs .env)
	@printf "$(BOLD)[*] Delete existing data from LINDAS$(NC)\n"
	@printf "$(GREY)"; \
	curl \
		--user $(USER):$(PASSWORD) \
		-X DELETE \
		"$(ENDPOINT)?graph=$(GRAPH)" || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)\n"

# 3. Set the modification date of the dataset (compares with the live graph)
stamp-metadata: $(PROCESSED_DATA) src/python/utils/graph_metadata.py | $(VENV)/.requirements-installed.stamp ## Set the modification date of the dataset by comparing with the graph on LINDAS
	@printf "$(BOLD)[*] Setting the modification date of the dataset$(NC)\n"
	@printf "$(GREY)"; \
	$(VENV_PYTHON) src/python/utils/graph_metadata.py --graph $(PROCESSED_DATA) --iri $(GRAPH) --endpoint $(ENDPOINT) --user $(USER) --password $(PASSWORD) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

# 4. Publish final graph to LINDAS
publish: test stamp-metadata delete ## Test, then replace the graph on LINDAS with the newly built one (needs .env)
	@printf "$(BOLD)[*] Upload final graph to LINDAS$(NC)\n"
	@printf "$(GREY)"; \
	curl \
		--user $(USER):$(PASSWORD) \
		-X POST \
		-H "Content-Type: text/turtle" \
		--data-binary @$(PROCESSED_DATA) \
		"$(ENDPOINT)?graph=$(GRAPH)" || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)\n"

# ==============================================================================
# CLEANUP
# ==============================================================================

clean: ## Remove all build artifacts, caches, the virtual environment, generated pages and rendered diagrams
	@printf "$(BOLD)[*] Cleaning build artifacts...$(NC)\n"
	@rm -rf $(BUILD_DIR) $(VENV) docs/*/entities.md docs/*/glossary.md docs/*/namespaces.md docs/*/assets/img
	@find . -path ./.git -prune -o \( -name __pycache__ -o -name .pytest_cache -o -name .quarto -o -name '*_files' -o -name '*_cache' -o -name '*.quarto_ipynb' -o -name .Rhistory -o -name .RData \) -prune -exec rm -rf {} +