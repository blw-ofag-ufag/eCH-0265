import pytest
from pathlib import Path
from rdflib import Graph
from pyshacl import validate

def test_glossary_shacl():
    """
    Checks if the file src/rdf/data/glossary.skos.ttl conforms to
    src/rdf/shapes/glossary.shacl.ttl.
    """
    data_path = Path("src/rdf/data/glossary.skos.ttl")
    shapes_path = Path("src/rdf/shapes/glossary.shacl.ttl")

    if not data_path.exists():
        pytest.skip(f"Data file not found: {data_path}")
    if not shapes_path.exists():
        pytest.skip(f"Shapes file not found: {shapes_path}")

    data_graph = Graph().parse(data_path, format="turtle")
    shapes_graph = Graph().parse(shapes_path, format="turtle")

    conforms, report_graph, report_text = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="none",
        meta_shacl=False,
        advanced=True,
        debug=False
    )

    if not conforms:
        pytest.fail(f"Glossary does not conform to SHACL shapes:\n\n{report_text}", pytrace=False)