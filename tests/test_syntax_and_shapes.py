import pytest
from pathlib import Path
import rdflib
from pyshacl import validate
from rdflib.graph import ReadOnlyGraphAggregate
from rdflib.namespace import Namespace, SH

ReadOnlyGraphAggregate.__hash__ = lambda self: id(self)


pytestmark = pytest.mark.filterwarnings(
    "ignore:Dataset.default_context is deprecated:DeprecationWarning",
    "ignore:.*Recursive Shape was detected.*"
)

from conftest import discover_all_ttl_files 

CROP = Namespace("https://agriculture.ld.admin.ch/crops/")

@pytest.mark.parametrize("filepath", discover_all_ttl_files(), ids=lambda p: p.name)
def test_turtle_syntax(filepath, parsed_ttl_cache):
    """
    Validates syntax for all discovered Turtle files by checking the session cache.
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
def test_shacl_compliance(data_fixture, request, datamodel_graph, cultivation_graph):
    target_graph = request.getfixturevalue(data_fixture)

    if data_fixture == "cultivation_graph":
        # Master graph validation: direct test against datamodel
        # No RDFS inference to prevent UniqueLang collisions
        conforms, results_graph, results_text = validate(
            data_graph=target_graph,
            shacl_graph=datamodel_graph,
            inference="none", 
            inplace=True, 
            debug=False
        )
    else:
        # Clone domain shapes into a standard Graph to safely mutate targets
        domain_shapes = rdflib.Graph()
        for triple in datamodel_graph:
            domain_shapes.add(triple)
            
        domain_shapes.remove((None, SH.targetClass, CROP.CultivationType))
        domain_shapes.remove((None, SH.targetClass, CROP.DeprecatedCultivationType))

        # Federate the target data and the master context
        evaluation_graph = ReadOnlyGraphAggregate([target_graph, cultivation_graph])

        # Validate with decoupled shapes and read-only aggregate
        conforms, results_graph, results_text = validate(
            data_graph=evaluation_graph,
            shacl_graph=domain_shapes,
            inference="none", 
            inplace=True, 
            debug=False
        )

    assert conforms, (
        f"SHACL Validation Failed for {data_fixture}!\n"
        f"--- SHACL Report ---\n{results_text}"
    )