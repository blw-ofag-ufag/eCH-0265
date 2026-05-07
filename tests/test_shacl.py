from pyshacl import validate

def test_cultivationtypes_shacl_compliance(ontology_graph, shacl_graph):
    """
    Validates cultivationtypes.ttl against the separated SHACL shapes in data-model.ttl.
    """
    # Run PySHACL validation
    conforms, results_graph, results_text = validate(
        ontology_graph,
        shacl_graph=shacl_graph,
        data_graph_format="turtle",
        shacl_graph_format="turtle",
        inference="rdfs", # Resolves rdfs:subClassOf logic for target targeting
        debug=False
    )

    # Assert and report exactly where it failed
    assert conforms, (
        f"SHACL Validation Failed for cultivationtypes.ttl!\n"
        f"--- SHACL Report ---\n{results_text}"
    )