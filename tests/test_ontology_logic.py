import os
import tempfile
import warnings
import pytest
from owlready2 import get_ontology, sync_reasoner, OwlReadyInconsistentOntologyError, Nothing
from pathlib import Path
from rdflib import Graph
from rdflib.graph import ReadOnlyGraphAggregate
from rdflib.namespace import RDFS, OWL, RDF

@pytest.fixture
def translated_ontology_path(cultivation_graph, core_graph):
    """
    Translates the combined in-memory rdflib graphs (core + cultivation) to RDF/XML
    and provides the temporary file path for Owlready2.
    """
    combined_graph = Graph()
    combined_graph += core_graph
    combined_graph += cultivation_graph

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
    Issues a warning if unused leaf nodes are found.
    """
    # FIX: Use ReadOnlyGraphAggregate to prevent O(N) graph duplication overhead
    combined_graph = ReadOnlyGraphAggregate([cultivation_graph, agis_graph, srppp_graph, naebi_graph])

    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX : <https://agriculture.ld.admin.ch/crops/>

    SELECT ?leaf
    WHERE {
        ?leaf a owl:Class .
        FILTER (STRSTARTS(STR(?leaf), "https://agriculture.ld.admin.ch/crops/cultivationtype/"))

        FILTER NOT EXISTS {
            ?subclass rdfs:subClassOf ?leaf .
        }

        FILTER NOT EXISTS {
            ?crop :cultivationType ?leaf .
        }
    }
    """
    results = list(combined_graph.query(query))
    
    if results:
        empty_leaves = [str(r.leaf) for r in results]
        
        warning_msg = (
            f"Found {len(empty_leaves)} empty leaf nodes in the cultivation hierarchy.\n"
            f"These nodes have no subclasses and are not used by any crops in AGIS, SRPPP, or NAEBI:\n"
        )
        for leaf in empty_leaves[:15]:
            warning_msg += f"  - {leaf}\n"
        if len(empty_leaves) > 15:
            warning_msg += f"  ... and {len(empty_leaves) - 15} more.\n"
            
        warnings.warn(warning_msg.strip(), UserWarning)


def test_no_unsatisfiable_classes_via_disjointness(cultivation_graph):
    """
    Searches for classes that become empty sets (unsatisfiable) because they are 
    directly or indirectly subclasses of two disjoint classes.
    """
    # FIX: Replaced exponentially complex SPARQL property paths with native Python graph traversal
    disjoint_pairs = set()

    # 1. Extract explicit disjointWith pairs
    for s, o in cultivation_graph.subject_objects(OWL.disjointWith):
        disjoint_pairs.add((s, o))

    # 2. Extract pairs from AllDisjointClasses lists
    for adc in cultivation_graph.subjects(RDF.type, OWL.AllDisjointClasses):
        members_list = cultivation_graph.value(adc, OWL.members)
        if members_list:
            members = list(cultivation_graph.items(members_list))
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    disjoint_pairs.add((members[i], members[j]))
                    disjoint_pairs.add((members[j], members[i]))

    errors = []
    
    # 3. Assess contradictory inheritance
    for cls in cultivation_graph.subjects(RDF.type, OWL.Class):
        # transitive_objects traverses the graph natively and executes in milliseconds
        superclasses = set(cultivation_graph.transitive_objects(cls, RDFS.subClassOf))
        
        for parent1, parent2 in disjoint_pairs:
            if parent1 in superclasses and parent2 in superclasses:
                b_class = str(cls).split('/')[-1]
                p1_name = str(parent1).split('/')[-1]
                p2_name = str(parent2).split('/')[-1]
                errors.append(f"  -> Class <{b_class}> contradictorily inherits from <{p1_name}> AND <{p2_name}>")

    if errors:
        error_msg = f"Ontology Error: Found {len(errors)} unsatisfiable classes (empty sets)!\n"
        error_msg += "These classes are subclasses of disjoint (mutually exclusive) concepts:\n"
        error_msg += "\n".join(errors)
        pytest.fail(error_msg.strip())