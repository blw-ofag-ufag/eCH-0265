import os
import tempfile
import warnings
import pytest
from owlready2 import get_ontology, sync_reasoner, OwlReadyInconsistentOntologyError, Nothing
from pathlib import Path
from rdflib import Graph
from rdflib.graph import ReadOnlyGraphAggregate
from rdflib.namespace import RDF, RDFS, OWL
from rdflib import URIRef

@pytest.fixture(scope="session")
def translated_ontology_path(cultivation_graph, core_graph):
    """
    Translates the combined rdflib graphs (core + cultivation) to RDF/XML
    and provides the temporary file path for Owlready2.
    """
    combined_graph = ReadOnlyGraphAggregate([core_graph, cultivation_graph])

    fd, temp_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)

    try:
        combined_graph.serialize(destination=temp_path, format="xml")
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


def test_no_empty_end_nodes(cultivation_graph, agis_graph, srppp_graph, naebi_graph):
    """
    Ensure all leaf nodes in the hierarchy are utilized by at least one 
    crop instance in the connected data systems (AGIS, SRPPP, NAEBI).
    """
    combined_graph = ReadOnlyGraphAggregate([
        cultivation_graph, 
        agis_graph, 
        srppp_graph, 
        naebi_graph
    ])

    CROP_NS = "https://agriculture.ld.admin.ch/crops/cultivationtype/"
    CULTIVATION_TYPE = URIRef("https://agriculture.ld.admin.ch/crops/cultivationType")

    # 1. Extract all target classes directly from the cultivation graph
    all_classes = {
        s for s in cultivation_graph.subjects(RDF.type, OWL.Class)
        if str(s).startswith(CROP_NS)
    }

    # 2. Identify all parent nodes (any node that is the target of a subClassOf relation)
    parents = set(combined_graph.objects(None, RDFS.subClassOf))

    # 3. Calculate leaf nodes natively
    leaves = all_classes - parents

    # 4. Extract all used cultivation types across the aggregate system
    used_types = set(combined_graph.objects(None, CULTIVATION_TYPE))

    # 5. Calculate empty leaves natively
    empty_leaves = leaves - used_types
    
    if empty_leaves:
        empty_leaves_list = sorted(list(empty_leaves))
        warning_msg = (
            f"Found {len(empty_leaves_list)} empty leaf nodes in the cultivation hierarchy.\n"
            f"These nodes have no subclasses and are not used by any crops in AGIS, SRPPP, or NAEBI:\n"
        )
        for leaf in empty_leaves_list[:15]:
            warning_msg += f"  - {str(leaf)}\n"
        if len(empty_leaves_list) > 15:
            warning_msg += f"  ... and {len(empty_leaves_list) - 15} more.\n"
            
        warnings.warn(warning_msg.strip(), UserWarning)


def get_all_ancestors(graph, node, memo, path=None):
    """Recursively fetches all ancestors for a given node with cycle detection."""
    if path is None:
        path = set()
    if node in memo:
        return memo[node]
    if node in path:
        return set()

    path.add(node)
    ancestors = set()
    for parent in graph.objects(node, RDFS.subClassOf):
        ancestors.add(parent)
        ancestors.update(get_all_ancestors(graph, parent, memo, path))

    path.remove(node)
    memo[node] = ancestors
    return ancestors


def test_no_unsatisfiable_classes_via_disjointness(cultivation_graph):
    """
    Searches for classes that become empty sets (unsatisfiable) because they are 
    directly or indirectly subclasses of two disjoint classes.
    """
    disjoint_pairs = set()

    # 1a. Extract direct owl:disjointWith relationships
    for s, o in cultivation_graph.subject_objects(OWL.disjointWith):
        disjoint_pairs.add((s, o))

    # 1b. Extract owl:AllDisjointClasses lists
    for adc in cultivation_graph.subjects(RDF.type, OWL.AllDisjointClasses):
        for member_list in cultivation_graph.objects(adc, OWL.members):
            members = list(cultivation_graph.items(member_list))
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    disjoint_pairs.add((members[i], members[j]))

    if not disjoint_pairs:
        return

    memo = {}
    errors = []

    # Identify all classes that are part of a subclass hierarchy
    classes_to_check = set(cultivation_graph.subjects(RDFS.subClassOf, None))
    classes_to_check.update(cultivation_graph.subjects(RDF.type, OWL.Class))

    # 2. Check each class against known disjoint pairs
    for cls in classes_to_check:
        ancestors = get_all_ancestors(cultivation_graph, cls, memo)
        ancestors.add(cls) # Include self to catch immediate disjoint contradictions

        for p1, p2 in disjoint_pairs:
            if p1 in ancestors and p2 in ancestors:
                errors.append((cls, p1, p2))

    if errors:
        error_msg = f"Ontology Error: Found {len(errors)} unsatisfiable classes (empty sets)!\n"
        error_msg += "These classes are subclasses of disjoint (mutually exclusive) concepts:\n"
        
        for b_class, p1, p2 in errors:
            b_id = str(b_class).split('/')[-1]
            p1_id = str(p1).split('/')[-1]
            p2_id = str(p2).split('/')[-1]
            error_msg += f"  -> Class <{b_id}> contradictorily inherits from <{p1_id}> AND <{p2_id}>\n"
            
        pytest.fail(error_msg.strip())