[![CI](https://github.com/blw-ofag-ufag/eCH-0265/actions/workflows/ci.yml/badge.svg)](https://github.com/blw-ofag-ufag/eCH-0265/actions/workflows/ci.yml)
[![GitHub last commit](https://img.shields.io/github/last-commit/blw-ofag-ufag/semantic-web-template.svg)](https://github.com/blw-ofag-ufag/eCH-0265/commits)
[![GitHub issues](https://img.shields.io/github/issues/blw-ofag-ufag/semantic-web-template.svg)](https://github.com/blw-ofag-ufag/eCH-0265/issues)

# Semantic web project template

For demonstrative purposes, this template repository includes a full semantic web pipeline, including
 
1. manual data curation (data files in `src/rdf/data`),
2. data integration from a relational database (using python, specifically `src/python/pipeline/...`),
3. OWL-based inferencing (using the ontology in `src/rdf/model.owl.ttl`),
4. SPARQL-based processing of the graph (using rules in `src/sparql/processing/...`)
5. SHACL-based graph data validation (using `src/rdf/shapes/model.shacl.ttl`)
6. a even more customizable Pytest test suite,
7. uploading of the final graph to LINDAS
8. a documentation building pipeline using Quarto

Specifically, this demo project creates a graph of around 120k triples from the Chinook database, makes some inferences, processes and validates the graph.

> [!IMPORTANT]
> After using this template repository for a project, you probably want to delete/overwrite any of the aforementioned turtle/sparql/python files.

## Development Tools

This template uses a variety of tools to ensure robust data integration, reasoning, validation, and documentation.

- [HermiT](http://www.hermit-reasoner.com/): An OWL reasoner used for logical reasoning and inferring new knowledge from the ontology and data.
- [Pytest](https://docs.pytest.org/): A testing framework used to run syntax checks and evaluate SHACL validation reports.
- [PySHACL](https://github.com/RDFLib/pySHACL): A Python engine used to validate the generated RDF graphs against SHACL shape definitions.
- [ROBOT](http://robot.obolibrary.org/): CLI tool used to merge, reason, and process RDF graphs.
- [RDFLib](https://rdflib.readthedocs.io/): A Python library used to parse, serialize, and programmatically manipulate RDF data.
- [Quarto](https://quarto.org/): An open-source publishing system used for rendering the documentation.

## Semantic Web Standards

The project relies on core W3C Semantic Web standards to model, link, and validate data effectively.

- [RDF (Resource Description Framework)](https://www.w3.org/RDF/): The foundational data model used to represent information as a directed graph of triples.
- [OWL (Web Ontology Language)](https://www.w3.org/OWL/): Used to define the formal semantics, classes, and properties of the ontology.
- [SHACL (Shapes Constraint Language)](https://www.w3.org/TR/shacl/): Used to declare structural constraints and validate the integrity of the RDF data.
- [SPARQL](https://www.w3.org/TR/sparql11-overview/): The standard query language used to extract, transform, and post-process the RDF graphs.
- [Turtle](https://www.w3.org/TR/turtle/): The primary, human-readable serialization format used for all RDF files in this repository.

## Build and Deployment Orchestration

To streamline the workflow, this project uses `make` as its primary orchestration tool, automating everything from setup to deployment. The `Makefile` defines a single entry point to sequentially execute data integration, logical reasoning, SPARQL updates, SHACL validation, testing, and documentation rendering.

1. Add variables to `.env` (for local execution)

    ``` sh
    USER=********
    PASSWORD=********
    GRAPH=********
    ENDPOINT=********
    ```

2. Set up dependencies

    ``` sh
    make setup
    ```

3. Run the build process

    ``` sh
    make
    ```

    Make sure you pass all tests with `pytest`.

4. Upload the final data to [LINDAS](https://lindas.admin.ch/), the linked data service by the federal archives:

    **Automatic Deployment**

    The deployment is automatically triggered via GitHub Actions whenever changes are pushed or merged to the `main` branch. 
    To enable this, configure the environment variables listed in step 1 as **repository secrets** in your GitHub project settings (`Settings > Secrets and variables > Actions > New repository secret`):

    **Manual Deployment**

    You can still upload the final data manually by running:

    ``` sh
    make publish
    ```

    By default, the publication process starts by deleting any pre-existing data in the provided named graph on LINDAS.
    You can also *just* delete any published data by running:

    ``` sh
    make delete
    ```

5. *If* you want to clean all written files:

    ``` sh
    make clean
    ```
