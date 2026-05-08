import os
import tempfile
import pytest
from owlready2 import get_ontology, sync_reasoner, OwlReadyInconsistentOntologyError, Nothing
from pathlib import Path

@pytest.fixture
def translated_ontology_path(cultivation_graph):
    """
    Translates the in-memory rdflib cultivation_graph to RDF/XML
    and provides the temporary file path for Owlready2.
    """
    fd, temp_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)

    try:
        cultivation_graph.serialize(destination=temp_path, format="xml")
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_cultivation_types_consistency(translated_ontology_path):
    """
    Test: Loads the RDF/XML ontology into Owlready2, runs the HermiT reasoner,
    and asserts both ABox consistency and TBox satisfiability.
    """
    try:
        onto_uri = Path(translated_ontology_path).resolve().as_uri()
        onto = get_ontology(onto_uri).load()
    except Exception as e:
        pytest.fail(f"Owlready2 failed to load the translated ontology: {e}")

    try:
        with onto:
            sync_reasoner()
    except OwlReadyInconsistentOntologyError as e:
        pytest.fail(f"Ontology data is INCONSISTENT. Reasoner output: {e}")

    unsatisfiable_classes = list(onto.classes())
    broken_classes = [cls for cls in unsatisfiable_classes if Nothing in cls.ancestors()]
    
    assert not broken_classes, (
        f"Ontology logic is invalid: Found UNSATISFIABLE classes "
        f"(empty sets due to contradictory axioms).\n"
        f"Broken classes: {[cls.name for cls in broken_classes]}"
    )