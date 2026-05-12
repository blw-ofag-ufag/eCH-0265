import os
import tempfile
import warnings
import pytest
from owlready2 import get_ontology, sync_reasoner, OwlReadyInconsistentOntologyError, Nothing
from pathlib import Path
from rdflib import Graph

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
    combined_graph = Graph()
    combined_graph += cultivation_graph
    combined_graph += agis_graph
    combined_graph += srppp_graph
    combined_graph += naebi_graph

    # SPARQL query to find classes that have NO subclasses (leaf nodes) 
    # AND have NO instances linking to them via :cultivationType
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX : <https://agriculture.ld.admin.ch/crops/>

    SELECT ?leaf
    WHERE {
        # Get all cultivation types
        ?leaf a owl:Class .
        FILTER (STRSTARTS(STR(?leaf), "https://agriculture.ld.admin.ch/crops/cultivationtype/"))

        # Must be a leaf node (nothing subclasses it)
        FILTER NOT EXISTS {
            ?subclass rdfs:subClassOf ?leaf .
        }

        # Must be empty (nothing uses it as its cultivationType)
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
    # This SPARQL query finds logical contradictions without requiring
    # an external reasoner or an XML export.
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT DISTINCT ?brokenClass ?parent1 ?parent2
    WHERE {
        # 1. Find all pairs of classes that are mutually exclusive (disjoint)
        {
            ?parent1 owl:disjointWith ?parent2 .
        } UNION {
            ?parent2 owl:disjointWith ?parent1 .
        } UNION {
            # Also handle the owl:AllDisjointClasses lists used in the code
            ?adc a owl:AllDisjointClasses ;
                 owl:members ?list .
            ?list rdf:rest*/rdf:first ?parent1 .
            ?list rdf:rest*/rdf:first ?parent2 .
            FILTER (?parent1 != ?parent2)
        }

        # 2. Find a class that is (directly or indirectly) a subclass of BOTH
        ?brokenClass rdfs:subClassOf+ ?parent1 .
        ?brokenClass rdfs:subClassOf+ ?parent2 .
    }
    """
    
    results = list(cultivation_graph.query(query))
    
    if results:
        error_msg = f"Ontology Error: Found {len(results)} unsatisfiable classes (empty sets)!\n"
        error_msg += "These classes are subclasses of disjoint (mutually exclusive) concepts:\n"
        
        for row in results:
            b_class = str(row.brokenClass).split('/')[-1]
            p1 = str(row.parent1).split('/')[-1]
            p2 = str(row.parent2).split('/')[-1]
            error_msg += f"  -> Class <{b_class}> contradictorily inherits from <{p1}> AND <{p2}>\n"
            
        pytest.fail(error_msg.strip())