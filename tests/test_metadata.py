from pathlib import Path
import re
import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

METADATA = Path("src/rdf/metadata.ttl")
ECH_CONFIG = Path("docs/_ech.yml")
SCHEMA_NAME = URIRef("http://schema.org/name")
SCHEMA_DESCRIPTION = URIRef("http://schema.org/description")
SCHEMA_DATASET = URIRef("http://schema.org/Dataset")


def doc_languages():
    return sorted(d.name for d in Path("docs").iterdir() if d.is_dir() and d.name in {"de", "fr", "it", "en"})


def configured_graph():
    match = re.search(r"^\s*graph:\s*(\S+)", ECH_CONFIG.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


@pytest.fixture(scope="module")
def metadata():
    if not METADATA.exists():
        pytest.skip(f"{METADATA} not found")
    g = Graph()
    g.parse(METADATA, format="turtle")
    return g


def test_metadata_describes_the_configured_graph(metadata):
    """The dataset in src/rdf/metadata.ttl is the named graph of docs/_ech.yml."""
    graph_iri = configured_graph()
    assert graph_iri, "docs/_ech.yml has no ech.graph entry"
    subjects = {s for s in metadata.subjects(RDF.type, SCHEMA_DATASET)}
    assert subjects == {URIRef(graph_iri)}, (
        f"src/rdf/metadata.ttl must describe exactly the named graph <{graph_iri}>, found {sorted(map(str, subjects))}"
    )


def test_metadata_is_translated(metadata):
    """Title and description of the dataset exist in every documentation language."""
    dataset = URIRef(configured_graph())
    for predicate in (SCHEMA_NAME, SCHEMA_DESCRIPTION):
        langs = {o.language for o in metadata.objects(dataset, predicate) if getattr(o, "language", None)}
        missing = set(doc_languages()) - langs
        assert not missing, f"{predicate} of the dataset lacks the languages {sorted(missing)}"


def test_metadata_has_no_fixed_modification_date(metadata):
    """The modification date is set by `make publish`, not maintained by hand."""
    dataset = URIRef(configured_graph())
    for predicate in (DCTERMS.modified, URIRef("http://schema.org/dateModified")):
        assert (dataset, predicate, None) not in metadata, f"remove {predicate} from src/rdf/metadata.ttl"
