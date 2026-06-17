# RDF master and reference data about crops

This project addresses the challenge of fragmented agricultural crop data within the Swiss federal administration, where essential systems[^1] all use separate, non-harmonized crop terminologies.
This lack of a "single source of truth" creates significant integration hurdles for digital tools.

In this project, we propose a unified master data system for crops and crop-related objects.
The repository implements a sustainable solution by using a dedicated RDF ontology (crops ontology) and a graph database on LINDAS.
This approach first connects (or "maps") the various crop terms from the different systems, creating a unified, machine-readable master data system that can be queried centrally.
This graph not only allows for complex queries across formerly siloed data but also provides the stable, versioned foundation for the long-term, step-by-step harmonization of crop data across the Swiss agricultural sector.

> [!WARNING]
> This project is still work in progress.

[^1]: For example [AGIS (direct payments)](https://www.i14y.admin.ch/en/catalog/concepts/08dcabe2-1734-ca16-9dfe-262056c9c124/content), [GRUD (fertilization)](https://www.agroscope.admin.ch/agroscope/de/home/themen/pflanzenbau/ackerbau/grud.html), [PSM registry (plant protection)](https://www.psm.admin.ch/de/kulturen/bs/A), [ProVar (varieties)](https://www.blw.admin.ch/de/sortenschutz#Sortenschutzregister), [PGREL-NIS (gene bank)](https://www.blw.admin.ch/de/pgrel-nis) and others.

# Data model

The general data model is doumented [here](https://shacl-play.sparna.fr/play/doc?format=html_respec&url=https%3A%2F%2Fraw.githubusercontent.com%2Fblw-ofag-ufag%2Fcrops%2Frefs%2Fheads%2Fmain%2Frdf%2Fshape%2Fdata-model.ttl&includeDiagram=true&sectionDiagram=true). Note that *SHACL Play!* reads the data from `rdf/shape/data-model.ttl` on `main`.
You may inspect the crop taxonomy/ontology using WebVOWL [here](https://service.tib.eu/webvowl/#iri=https://raw.githubusercontent.com/blw-ofag-ufag/crops/refs/heads/main/rdf/processed/crop-taxonomy.ttl) or read its turtle file [here](https://raw.githubusercontent.com/blw-ofag-ufag/crops/refs/heads/main/rdf/ontology/cultivationtypes.ttl).

> [!NOTE]
> You may find more information on the [repository wiki](https://github.com/blw-ofag-ufag/crops/wiki).

# Repository structure

- `/data`: source data files
- `/docs`: (static) html documents, rendered as github page
- `/rdf`: all RDF (turtle) files
  - `/data`: tabular data
  - `/ontology`: core vocabulary, crop taxonomy
  - `/processed`: any automatically written turtle files -- do not change (manually)
  - `/shape`: dedicated files for SHACL shapes
- `/src`: source code
- `/tests`: pytest files

# Run the data processing and LINDAS integration pipeline

The data integration pipeline uses all the R and python scripts in the `/scripts` folder. The entire pipeline can be triggered with:

1. Add variables to `.env`

    ```sh
    USER=lindas-foag
    PASSWORD=********
    GRAPH=https://lindas.admin.ch/foag/crops
    ENDPOINT=https://stardog.cluster.ldbar.ch/lindas
    EPPO=********
    ```

2. Start a virtual environment and install libraries:

    ``` sh
    python -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    pip install --upgrade pip
    pip install -r src/python/requirements.txt
    ```

3. Run the ETL pipeline:

    ``` sh
    bash src/pipeline.bash
    ```

    This pipeline

    1. validates syntax of all RDF turtle files,
    2. constructs a graph with inferred triples (based on the OWL-ontology),
    3. validates the final graph based on the SHACL data model and
    4. overrides the named graph <https://lindas.admin.ch/foag/crops> on LINDAS.

4. Make sure you pass all tests with `pytest`:

    ``` sh
    pytest tests/ -v
    ```

5. Check out the results on LINDAS. ([Here's an example entity.](https://agriculture.ld.admin.ch/crops/cultivationtype/413))

# How can I use this data?

You can query the crop master data system using the [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/).
Here's [an example query](https://s.zazuko.com/3xUUXpv) that gets you all cultivation type URIs and labels in German:

``` sparql
PREFIX schema: <http://schema.org/>
PREFIX owl: <http://www.w3.org/2002/07/owl#> 
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX : <https://agriculture.ld.admin.ch/crops/>

SELECT ?name ?URI
FROM <https://lindas.admin.ch/foag/crops>
WHERE {
  ?URI a owl:Class ;
    schema:name ?name ;
    rdfs:subClassOf+ :Cultivation .
  FILTER(LANG(?name) = "de")
}
ORDER BY ?name
```

More examples are available in [`src/sparql/queries`](src/sparql/queries). Note that some of these examples are "parametrized" and thus can't be run without modifications.

In order to automatically retrieve data from LINDAS, you can send a POST request to the LINDAS endpoint, passing the SPARQL query as a parameter.

``` sh
# define any query you want...
query="SELECT * FROM <https://lindas.admin.ch/foag/crops> WHERE { ?s ?p ?o }"
curl -G "https://lindas.admin.ch/query" \
     --data-urlencode "query=$query" \
     -H "Accept: application/json"
```

Depending on your integration needs, you can adjust the accept header to retrieve the data in several possible formats, including JSON (`application/json`), XML (`application/sparql-results+xml`) or CSV (`text/csv`).
