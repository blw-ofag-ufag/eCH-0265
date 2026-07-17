import pytest
import warnings
from rdflib import Graph, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")

def get_shacl_rules():
    """
    Parses the SHACL definition file during Pytest collection
    to generate one distinct test per Shape or Constraint.
    """
    g = Graph()
    try:
        g.parse("src/rdf/shapes/model.shacl.ttl", format="turtle")
    except Exception:
        return []
        
    query = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX schema: <http://schema.org/>

        SELECT DISTINCT ?shape ?type ?name ?message ?path
        WHERE {
            {
                ?shape a sh:NodeShape .
                BIND("NodeShape" AS ?type)
            }
            UNION
            {
                [] sh:property ?shape .
                BIND("Property" AS ?type)
            }
            UNION
            {
                [] sh:sparql ?shape .
                BIND("SPARQL" AS ?type)
            }
            OPTIONAL { ?shape schema:name|sh:name|rdfs:label|rdfs:comment ?name . }
            OPTIONAL { ?shape sh:message|dcterms:description ?message . }
            OPTIONAL { ?shape sh:path ?path . }
        }
    """

    shapes_dict = {}
    for row in g.query(query):
        s = row.shape
        if s not in shapes_dict:
            shapes_dict[s] = {
                "type": str(row.type),
                "messages": set(),
                "names": set(),
                "paths": set(),
                "shape_uri": str(s) if isinstance(s, URIRef) else None
            }
            
        if row.message:
            shapes_dict[s]["messages"].add(str(row.message))
        if row.name:
            shapes_dict[s]["names"].add(str(row.name))
        if row.path:
            shapes_dict[s]["paths"].add(str(row.path))
            
    rules = []
    for s, data in shapes_dict.items():
        # Create a user-friendly test name for the terminal
        if data["messages"]:
            test_name = sorted(data["messages"])[0]
        elif data["names"]:
            # Prefer shorter names/labels over long descriptions/comments
            test_name = sorted(data["names"], key=len)[0]
        elif data["paths"]:
            test_name = f"Property {sorted(data['paths'])[0].split('/')[-1].split('#')[-1]}"
        else:
            test_name = f"Unnamed {data['type']}"

        rules.append({
            "test_name": test_name,
            "type": data["type"],
            "message": sorted(data["messages"])[0] if data["messages"] else None,
            "path": sorted(data["paths"])[0] if data["paths"] else None,
            "shape_uri": data["shape_uri"]
        })

    # Deduplicate rules by their test name
    unique_rules = {r["test_name"]: r for r in rules}
    return list(unique_rules.values())

# Extract the rules so Pytest can parameterize them
RULES = get_shacl_rules()

@pytest.fixture(scope="session")
def shacl_report():
    """Loads the pre-generated SHACL validation report exactly once."""
    g = Graph()
    try:
        g.parse("build/rdf/04-shacl-report.ttl", format="turtle")
    except Exception as e:
        pytest.fail(f"Could not load SHACL report. Did PySHACL run? Error: {e}")
    return g

def test_shacl_report_is_populated(shacl_report):
    """Ensures that the SHACL report actually contains validation data."""
    if len(shacl_report) == 0:
        pytest.fail("The SHACL report graph is completely empty. PySHACL may have failed silently.")
        
    query = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        ASK { ?report a sh:ValidationReport }
    """
    
    # Evaluate the ASK query. QueryResult from an ASK query yields a boolean.
    has_report = False
    for res in shacl_report.query(query):
        has_report = bool(res)
        
    if not has_report:
        pytest.fail("The SHACL report does not contain a sh:ValidationReport node. Validation likely failed.")

@pytest.mark.parametrize("rule", RULES, ids=lambda r: f"{r['type']} | {r['test_name']}")
def test_shacl_rule(rule, shacl_report):
    """Evaluates an individual SHACL constraint against the validation report."""
    
    # We must match Rules to Report results. Since Blank Nodes do not map 
    # reliably across different RDF graphs, we match by Message, Path, or URI.
    if rule["message"]:
        msg_literal = rule["message"].replace('"', '\\"')
        filter_str = f'STR(?actualMessage) = "{msg_literal}"'
    elif rule["path"]:
        filter_str = f'?path = <{rule["path"]}>'
    elif rule["shape_uri"]:
        filter_str = f'?sourceShape = <{rule["shape_uri"]}>'
    else:
        pytest.skip("Rule has no URI, message, or path to map to report results.")
        
    query = f"""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT ?focusNode ?severity ?actualMessage
        WHERE {{
            ?report a sh:ValidationReport ;
                    sh:result ?result .
            ?result sh:focusNode ?focusNode ;
                    sh:resultSeverity ?severity .
            OPTIONAL {{ ?result sh:resultMessage ?actualMessage . }}
            OPTIONAL {{ ?result sh:resultPath ?path . }}
            OPTIONAL {{ ?result sh:sourceShape ?sourceShape . }}
            
            # Inject the specific match condition for this rule
            FILTER( {filter_str} )
        }}
    """
    
    warnings_list = []
    errors_list = []
    infos_list = []
    
    for row in shacl_report.query(query):
        node = str(row.focusNode).split("#")[-1].split("/")[-1] if row.focusNode else "Unknown Node"
        if row.severity == SH.Violation:
            errors_list.append(node)
        elif row.severity == SH.Warning:
            warnings_list.append(node)
        elif row.severity == SH.Info:
            infos_list.append(node)
            
    def format_nodes(nodes, limit=5):
        displayed = ", ".join(f"ex:{n}" for n in nodes[:limit])
        if len(nodes) > limit:
            displayed += f", and {len(nodes) - limit} more"
        return displayed

    # Emit native Pytest warnings for non-violating severities
    if infos_list:
        warnings.warn(f"SHACL INFO for '{rule['test_name']}': {format_nodes(infos_list)}", UserWarning)
        
    if warnings_list:
        warnings.warn(f"SHACL WARNING for '{rule['test_name']}': {format_nodes(warnings_list)}", UserWarning)
        
    # Trigger native Pytest failure for Violations
    if errors_list:
        pytest.fail(
            f"SHACL Violation '{rule['test_name']}' failed on {len(errors_list)} node(s):\n" +
            f"Nodes: {format_nodes(errors_list)}",
            pytrace=False
        )