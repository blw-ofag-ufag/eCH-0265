import pytest
import requests
import csv
import io
from rdflib import Graph

# Configuration
RDF_FILE_PATH = "./rdf/data/srppp.ttl"
CORE_RDF_PATH = "./rdf/ontology/core.ttl"
CSV_URL = "https://raw.githubusercontent.com/BLV-OSAV-USAV/PSMV-RDF/refs/heads/main/data/raw/Code.csv"

def test_culture_consistency_in_rdf():
    """
    Tests that the hierarchy (ID, PARENT_ID) AND the localized names (ID, LANGUAGE, VALUE)
    in the remote CSV (for TEXT_KEY == 'Culture') EXACTLY MATCH the local RDF graph.
    """
    
    # ==========================================
    # 1. Fetch and process the remote CSV data
    # ==========================================
    try:
        response = requests.get(CSV_URL, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Failed to download CSV from {CSV_URL}\nError: {e}")

    csv_hierarchy = set()
    csv_names = set()
    
    reader = csv.DictReader(io.StringIO(response.text))
    
    for row in reader:
        if row.get("TEXT_KEY") == "Culture":
            c_id = str(row.get("ID", "")).strip()
            c_parent_id = str(row.get("PARENT_ID", "")).strip()
            c_lang = str(row.get("LANGUAGE", "")).strip().lower()
            c_val = str(row.get("VALUE", "")).strip()
            
            # Populate Hierarchy Set
            if c_id and c_parent_id:
                csv_hierarchy.add((c_id, c_parent_id))
            
            # Populate Names Set
            if c_id and c_lang and c_val:
                csv_names.add((c_id, c_lang, c_val))
                
    if not csv_hierarchy and not csv_names:
        pytest.fail("The CSV filter returned 0 results. Check if the CSV structure changed.")

    # ==========================================
    # 2. Parse the RDF file
    # ==========================================
    g = Graph()
    try:
        g.parse(RDF_FILE_PATH, format="turtle")
        g.parse(CORE_RDF_PATH, format="turtle")
    except Exception as e:
        pytest.fail(f"Failed to parse the local RDF file at {RDF_FILE_PATH}\nError: {e}")

    # ==========================================
    # 3. Extract RDF Hierarchy and Names
    # ==========================================
    rdf_hierarchy = set()
    rdf_names = set()

    # Query 1: Hierarchy
    sparql_hierarchy = """
    PREFIX cube: <https://cube.link/>
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?id ?parent_id
    WHERE {
      [
        a/rdfs:subClassOf* cube:Observation ;
        schema:identifier ?id ;
        schema:isPartOf / schema:identifier ?parent_id
      ]
    }
    """
    for row in g.query(sparql_hierarchy):
        rdf_hierarchy.add((str(row.id).strip(), str(row.parent_id).strip()))

    # Query 2: Localized Names
    sparql_names = """
    PREFIX cube: <https://cube.link/>
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?id ?name
    WHERE {
      ?obs a/rdfs:subClassOf* cube:Observation ;
           schema:identifier ?id ;
           schema:name ?name .
    }
    """
    for row in g.query(sparql_names):
        r_id = str(row.id).strip()
        r_val = str(row.name).strip()
        # Extract the language tag (e.g., 'de' from "Gladiole"@de)
        r_lang = str(row.name.language).lower() if row.name.language else ""
        rdf_names.add((r_id, r_lang, r_val))

    # ==========================================
    # 4. Validation and Error Reporting
    # ==========================================
    
    # Calculate bidirectional differences for both datasets
    missing_hierarchy_in_rdf = csv_hierarchy - rdf_hierarchy
    extra_hierarchy_in_rdf = rdf_hierarchy - csv_hierarchy
    
    missing_names_in_rdf = csv_names - rdf_names
    extra_names_in_rdf = rdf_names - csv_names
    
    # If any set is not empty, we compile a master error message
    if any([missing_hierarchy_in_rdf, extra_hierarchy_in_rdf, missing_names_in_rdf, extra_names_in_rdf]):
        error_msg = "Exact match validation failed between CSV and RDF graph.\n\n"
        
        # --- HIERARCHY ERRORS ---
        if missing_hierarchy_in_rdf:
            error_msg += f"[{len(missing_hierarchy_in_rdf)} MISSING HIERARCHY IN RDF] Found in CSV, but not in RDF:\n"
            for m_id, m_parent in list(missing_hierarchy_in_rdf)[:10]:
                error_msg += f"  → ID: {m_id} | PARENT_ID: {m_parent}\n"
            if len(missing_hierarchy_in_rdf) > 10:
                error_msg += f"  ... and {len(missing_hierarchy_in_rdf) - 10} more.\n"
            error_msg += "\n"

        if extra_hierarchy_in_rdf:
            error_msg += f"[{len(extra_hierarchy_in_rdf)} EXTRA HIERARCHY IN RDF] Found in RDF, but not in CSV:\n"
            for e_id, e_parent in list(extra_hierarchy_in_rdf)[:10]:
                error_msg += f"  → ID: {e_id} | PARENT_ID: {e_parent}\n"
            if len(extra_hierarchy_in_rdf) > 10:
                error_msg += f"  ... and {len(extra_hierarchy_in_rdf) - 10} more.\n"
            error_msg += "\n"

        # --- NAME ERRORS ---
        if missing_names_in_rdf:
            error_msg += f"[{len(missing_names_in_rdf)} MISSING NAMES IN RDF] Found in CSV, but not in RDF:\n"
            for m_id, m_lang, m_val in list(missing_names_in_rdf)[:10]:
                error_msg += f"  → ID: {m_id} | LANG: '{m_lang}' | VALUE: '{m_val}'\n"
            if len(missing_names_in_rdf) > 10:
                error_msg += f"  ... and {len(missing_names_in_rdf) - 10} more.\n"
            error_msg += "\n"

        if extra_names_in_rdf:
            error_msg += f"[{len(extra_names_in_rdf)} EXTRA NAMES IN RDF] Found in RDF, but not in CSV:\n"
            for e_id, e_lang, e_val in list(extra_names_in_rdf)[:10]:
                error_msg += f"  → ID: {e_id} | LANG: '{e_lang}' | VALUE: '{e_val}'\n"
            if len(extra_names_in_rdf) > 10:
                error_msg += f"  ... and {len(extra_names_in_rdf) - 10} more.\n"

        pytest.fail(error_msg.strip())