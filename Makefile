# ==============================================================================
# CONFIG
# ==============================================================================

# Directories
BUILD_DIR        := build
RDF_DIR          := $(BUILD_DIR)/rdf
PYTHON_DIR       := src/python

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
SHACL_PLAY_VERSION := 0.12.2
SHACL_PLAY_JAR     := $(VENV_BIN)/shacl-play-app.jar
PLANTUML_VERSION   := 1.2024.3
PLANTUML_JAR       := $(VENV_BIN)/plantuml.jar
VENV_JAVA_DIR      := $(VENV)/java17
JAVA17             := $(VENV_JAVA_DIR)/jdk-17.0.2/bin/java

# Inputs
ONTO             := $(wildcard src/rdf/ontology/*.owl.ttl)
DATA             := $(wildcard src/rdf/data/*.ttl)
SHAPES           := src/rdf/shapes/model.shacl.ttl
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
IMG_DIR          := $(BUILD_DIR)/img
UML_PUML         := $(IMG_DIR)/uml.puml
DOCS_IMG_DIR     := $(DOCS_DIR)/assets/img
DOCS_UML_PNG     := $(DOCS_IMG_DIR)/uml.png

# Logs
LOG_DIR          := $(BUILD_DIR)/log
MERGE_LOG        := $(LOG_DIR)/01-merge.log
INFER_LOG        := $(LOG_DIR)/02-infer.log
QUERY_LOG        := $(LOG_DIR)/03-query.log
SHACL_LOG        := $(LOG_DIR)/04-shacl.log
QUARTO_LOG       := $(LOG_DIR)/05-quarto.log
SHACL_PLAY_LOG   := $(LOG_DIR)/06-shacl-play.log

# Colors for logging
RED              := \033[0;31m
GREY             := \033[0;90m
BOLD             := \033[1;37m
NC               := \033[0m

.PHONY: all robot test docs clean check-python venv install-dependencies setup build delete publish generate-shacl-docs generate-glossary-docs

# Default target
all: test docs

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

# 4. Install robot
$(VENV_BIN)/robot.jar: | $(VENV_PYTHON)
	@printf "$(BOLD)[*] Downloading ROBOT ontology tool...$(NC)\n"
	@printf "$(GREY)"; curl -sL https://github.com/ontodev/robot/releases/download/$(ROBOT_VERSION)/robot.jar -o $(VENV_BIN)/robot.jar || { printf "$(NC)"; exit 1; }; printf "$(NC)"

robot: $(VENV_BIN)/robot.jar

# 5. Install SHACL Play
$(SHACL_PLAY_JAR): | $(VENV_PYTHON)
	@printf "$(BOLD)[*] Downloading SHACL Play...$(NC)\n"
	@printf "$(GREY)"; curl -sLf https://github.com/sparna-git/shacl-play/releases/download/$(SHACL_PLAY_VERSION)/shacl-play-app-$(SHACL_PLAY_VERSION)-onejar.jar -o $(SHACL_PLAY_JAR) || \
	(printf "$(NC)\n$(RED)ERROR: Download failed. Check the version/URL.$(NC)\n" && rm -f $(SHACL_PLAY_JAR) && exit 1); printf "$(NC)"

# 6. Install PlantUML (for root-free pure Java rendering)
$(PLANTUML_JAR): | $(VENV_PYTHON)
	@printf "$(BOLD)[*] Downloading PlantUML...$(NC)\n"
	@printf "$(GREY)"; curl -sLf https://github.com/plantuml/plantuml/releases/download/v$(PLANTUML_VERSION)/plantuml-$(PLANTUML_VERSION).jar -o $(PLANTUML_JAR) || \
	(printf "$(NC)\n$(RED)ERROR: Download failed. Check the version/URL.$(NC)\n" && rm -f $(PLANTUML_JAR) && exit 1); printf "$(NC)"

# 7. Install local Java 17 for SHACL Play and PlantUML
$(JAVA17): | $(VENV)
	@printf "$(BOLD)[*] Downloading portable Java 17...$(NC)\n"
	@printf "$(GREY)"; mkdir -p $(VENV_JAVA_DIR); \
	curl -sL https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_linux-x64_bin.tar.gz | tar -xz -C $(VENV_JAVA_DIR) || { printf "$(NC)"; exit 1; }; printf "$(NC)"

# ==============================================================================
# RDF DATA INTEGRATION, REASONING AND POST-PROCESSING
# ==============================================================================

# 1. Set up directories
$(RDF_DIR) $(LOG_DIR) $(IMG_DIR) $(BUILD_DIR):
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
$(LOG_DIR)/syntax-check.stamp: $(DATA) $(ONTO) $(SHAPES) $(PREFIXES) $(FETCHED_DATA) tests/test_syntax.py | $(LOG_DIR) $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Checking Turtle syntax...$(NC)\n"
	@printf "$(GREY)"; \
	$(PYTEST) tests/test_syntax.py -q > /dev/null 2>&1 || { printf "$(NC)\n$(RED)[ERROR] Syntax check failed:$(NC)\n"; $(PYTEST) tests/test_syntax.py -v; exit 1; }; \
	printf "$(NC)"
	@touch $@

# 4. Merge ontology, shapes, static data, fetched data, and prefixes
$(MERGED_DATA): $(ONTO) $(SHAPES) $(DATA) $(FETCHED_DATA) $(PREFIXES) $(LOG_DIR)/syntax-check.stamp src/python/utils/turtle_serializer.py | $(LOG_DIR) $(VENV_BIN)/robot.jar $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Merging ontology, shapes and data...$(NC)\n"
	@printf "$(GREY)"; \
	$(ROBOT) merge \
		$(foreach o,$(ONTO),--input $(o)) \
		--input $(SHAPES) \
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
build: $(PROCESSED_DATA)

# ==============================================================================
# BUILD DOCUMENTATION
# ==============================================================================

$(DOCS_UML_PNG): $(SHAPES) | $(IMG_DIR) $(LOG_DIR) $(SHACL_PLAY_JAR) $(PLANTUML_JAR) $(JAVA17)
	@mkdir -p $(DOCS_IMG_DIR)
	@printf "$(BOLD)[*] Extracting UML structure via SHACL Play...$(NC)\n"
	@printf "$(GREY)"; \
	$(JAVA17) -jar $(SHACL_PLAY_JAR) draw -i $(SHAPES) -o $(UML_PUML) > $(SHACL_PLAY_LOG) 2>&1 || { printf "$(NC)\n$(RED)ERROR: SHACL Play failed. See log below:$(NC)\n$(GREY)"; cat $(SHACL_PLAY_LOG); printf "$(NC)\n"; exit 1; }; \
	test -f shacl-play-app.log && mv shacl-play-app.log $(LOG_DIR)/ 2>/dev/null || true; \
	printf "$(NC)"
	@printf "$(BOLD)[*] Rendering PNG with PlantUML (Pure Java Smetana engine)...$(NC)\n"
	@printf "$(GREY)"; \
	awk '/@startuml/{print;print "!pragma layout smetana";next}1' $(UML_PUML) > $(UML_PUML).tmp && mv $(UML_PUML).tmp $(UML_PUML); \
	$(JAVA17) -jar $(PLANTUML_JAR) -tpng $(UML_PUML) -o $(shell cd $(IMG_DIR) && pwd) || { printf "$(NC)"; exit 1; }; \
	cp $(IMG_DIR)/uml.png $(DOCS_UML_PNG); \
	printf "$(NC)"

generate-shacl-docs: $(SHAPES) $(PREFIXES) src/python/utils/generate_shacl_docs.py | $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Generating SHACL documentation...$(NC)\n"
	@printf "$(GREY)"; \
	$(VENV_PYTHON) src/python/utils/generate_shacl_docs.py -i $(SHAPES) -d $(DOCS_DIR) -p $(PREFIXES) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

generate-glossary-docs: src/rdf/data/glossary.skos.ttl $(PREFIXES) src/python/utils/generate_glossary_docs.py | $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Generating glossary documentation...$(NC)\n"
	@printf "$(GREY)"; \
	$(VENV_PYTHON) src/python/utils/generate_glossary_docs.py -i src/rdf/data/glossary.skos.ttl -d $(DOCS_DIR) -p $(PREFIXES) || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)"

docs: $(SHACL_REPORT) generate-shacl-docs generate-glossary-docs $(DOCS_UML_PNG)
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
test: build $(SHACL_REPORT) | $(VENV)/.requirements-installed.stamp
	@printf "$(BOLD)[*] Running final test suite...$(NC)\n"
	@$(PYTEST) tests/ -v

# ==============================================================================
# PUBLICATION
# ==============================================================================

# 1. Import environment variables natively into Make
-include .env
export

# 2. Delete the existing data from LINDAS
delete:
	@printf "$(BOLD)[*] Delete existing data from LINDAS$(NC)\n"
	@printf "$(GREY)"; \
	curl \
		--user $(USER):$(PASSWORD) \
		-X DELETE \
		"$(ENDPOINT)?graph=$(GRAPH)" || { printf "$(NC)"; exit 1; }; \
	printf "$(NC)\n"

# 3. Publish final graph to LINDAS
publish: test delete
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

clean:
	@printf "$(BOLD)[*] Cleaning build artifacts...$(NC)\n"
	@rm -rf $(BUILD_DIR) $(VENV) .quarto docs/.quarto tests/__pycache__ docs/index_files docs/*/entities.md docs/*/glossary.md