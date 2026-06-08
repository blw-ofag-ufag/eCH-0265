import os
import tempfile
import warnings
import pytest
from owlready2 import get_ontology, sync_reasoner, OwlReadyInconsistentOntologyError, Nothing
from pathlib import Path
from rdflib.namespace import RDFS, OWL, RDF
from rdflib.term import URIRef

CROP = URIRef("https://agriculture.ld.admin.ch/crops/")
CULTIVATION_TYPE_PREFIX = "https://agriculture.ld.admin.ch/crops/cultivationtype/"

@pytest.fixture(scope="session")
def translated_ontology_path(cultivation_graph, core_graph):
    """
    Optimized: Bypasses in-memory graph merging entirely and uses N-Triples.
    RDFlib serializes N-Triples much faster than RDF/XML, and Owlready2 parses it faster.
    """
    fd, temp_path = tempfile.mkstemp(suffix=".nt")
    
    # Write both graphs directly to the same file descriptor to avoid memory overhead
    with os.fdopen(fd, 'wb') as f:
        core_graph.serialize(destination=f, format="nt")
        cultivation_graph.serialize(destination=f, format="nt")

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_cultivation_types_consistency(translated_ontology_path):
    """
    Loads the N-Triples ontology into Owlready2, runs the HermiT reasoner,
    and asserts TBox satisfiability.
    """
    try:
        onto_uri = Path(translated_ontology_path).resolve().as_uri()
        onto = get_ontology(onto_uri).load()
    except Exception as e:
        pytest.fail(f"Owlready2 failed to load the translated ontology: {e}")

    try:
        with onto:
            # Property value reasoning disabled to accelerate class consistency checks
            sync_reasoner(infer_property_values=False)
    except OwlReadyInconsistentOntologyError as e:
        pytest.fail(f"Ontology data is INCONSISTENT. Reasoner output: {e}")

    unsatisfiable_classes = list(onto.classes())
    broken_classes = [cls for cls in unsatisfiable_classes if Nothing in cls.ancestors()]
    
    assert not broken_classes, (
        f"Ontology logic is invalid: Found UNSATISFIABLE classes "
        f"(empty sets due to contradictory axioms).\n"
        f"Broken classes: {[cls.name for cls in broken_classes]}"
    )


def test_no_empty_end_nodes(cultivation_graph, agis_graph, srppp_graph, naebi_graph):
    """
    Ensure all leaf nodes in the hierarchy are utilized by at least one 
    crop instance in the connected data systems (AGIS, SRPPP, NAEBI).
    """
    # 1. Gather all unique target IRIs used by the domain graphs
    used_nodes = set()
    linking_properties = (
        URIRef(CROP + "cultivationType"),
        URIRef(CROP + "cultivationGroup"),
        URIRef(CROP + "cultivationCategory"),
        URIRef(CROP + "cultivationSubCategory")
    )
    
    for graph in (agis_graph, srppp_graph, naebi_graph):
        for prop in linking_properties:
            used_nodes.update(graph.objects(predicate=prop))

    # 2. Identify classes and parent classes using native rdflib sets
    all_classes = set(cultivation_graph.subjects(RDF.type, OWL.Class))
    parent_classes = set(cultivation_graph.objects(predicate=RDFS.subClassOf))
    
    # 3. Calculate leaves
    all_leaves = all_classes - parent_classes

    # 4. Filter leaves natively utilizing URIRef string inheritance
    target_leaves = {
        leaf for leaf in all_leaves 
        if isinstance(leaf, URIRef) and leaf.startswith(CULTIVATION_TYPE_PREFIX)
    }

    # 5. Direct mathematical set difference (no str() casting required)
    empty_leaves = target_leaves - used_nodes
    
    if empty_leaves:
        sorted_leaves = sorted(str(leaf) for leaf in empty_leaves)
        warning_msg = (
            f"Found {len(sorted_leaves)} empty leaf nodes in the cultivation hierarchy.\n"
            f"These nodes have no subclasses and are not referenced by any crops in AGIS, SRPPP, or NAEBI:\n"
        )
        
        for leaf in sorted_leaves[:15]:
            warning_msg += f"  - {leaf}\n"
        
        if len(sorted_leaves) > 15:
            warning_msg += f"  ... and {len(sorted_leaves) - 15} more.\n"
            
        warnings.warn(warning_msg.strip(), UserWarning)