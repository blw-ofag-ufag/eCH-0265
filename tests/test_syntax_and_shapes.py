import pytest
from pathlib import Path
from pyshacl import validate

# Import the discovery function to keep the parameterization DRY
from conftest import discover_all_ttl_files 

@pytest.mark.parametrize("filepath", discover_all_ttl_files(), ids=lambda p: p.name)
def test_turtle_syntax(filepath, parsed_ttl_cache):
    """
    Validates syntax for all discovered Turtle files by checking the session cache.
    Eliminates redundant parsing while maintaining blanket coverage.
    """
    _, err = parsed_ttl_cache.get(filepath, (None, Exception("File missing from cache.")))
    
    if err:
        pytest.fail(f"Syntax validation failed for {filepath.name}\nDetails: {str(err)}")

@pytest.mark.parametrize("data_fixture", [
    "cultivation_graph",
    "agis_graph",
    "srppp_graph",
    "naebi_graph"
])
def test_shacl_compliance(data_fixture, request, datamodel_graph):
    """
    Validates data graphs against the SHACL shapes in data-model.ttl.
    Strictly mirrors the CLI execution: pyshacl -s data-model.ttl -i rdfs -f human <file>
    """
    data_graph = request.getfixturevalue(data_fixture)

    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=datamodel_graph,
        data_graph_format="turtle",
        shacl_graph_format="turtle",
        inference="rdfs", 
        debug=False
    )

    assert conforms, (
        f"SHACL Validation Failed for {data_fixture}!\n"
        f"--- SHACL Report ---\n{results_text}"
    )