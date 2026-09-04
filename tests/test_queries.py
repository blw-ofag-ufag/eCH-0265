import json
import urllib.request
import urllib.parse
from pathlib import Path
import pytest

def get_queries():
    """Fetches all SPARQL files inside the queries directory."""
    return list(Path("src/sparql/queries").rglob("*.rq"))

@pytest.mark.parametrize("query_file", get_queries(), ids=lambda p: p.name)
def test_example_queries(query_file):
    """
    Checks that the query has a descriptive comment and actually 
    returns records when executed against LINDAS.
    """
    content = query_file.read_text(encoding="utf-8").strip()
    lines = content.splitlines()
    
    # Check for first line documentation formatting
    assert lines, f"Query file {query_file.name} is empty"
    assert lines[0].strip().startswith("#"), f"First line of {query_file.name} must be a comment starting with #"
    assert len(lines[0].strip()) > 2, f"Comment in {query_file.name} must contain a description"
    
    # Automatically check if it returns something from LINDAS
    url = "https://agriculture.ld.admin.ch/query"
    
    headers = {
        "Accept": "application/sparql-results+json, application/ld+json, application/n-triples, text/turtle",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = urllib.parse.urlencode({"query": content}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            assert response.getcode() == 200, f"Endpoint responded with HTTP {response.getcode()}"
            
            content_type = response.headers.get("Content-Type", "")
            response_body = response.read().decode("utf-8")
            
            # Handling standard SPARQL SELECT or ASK queries
            if "application/sparql-results+json" in content_type or "application/json" in content_type:
                response_data = json.loads(response_body)
                
                if "results" in response_data and "bindings" in response_data["results"]:
                    assert len(response_data["results"]["bindings"]) > 0, "SELECT query returned no results."
                elif "boolean" in response_data:
                    assert response_data["boolean"] is True, "ASK query returned false."
            
            # Handling DESCRIBE/CONSTRUCT queries
            else:
                assert len(response_body.strip()) > 0, "Graph query returned empty results."
                
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        pytest.fail(f"HTTPError {e.code} for query {query_file.name}: {error_msg}")
    except Exception as e:
        pytest.fail(f"Failed to execute query {query_file.name}: {e}")