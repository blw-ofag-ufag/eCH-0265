import io
import os
import csv
import gzip
import warnings
from pathlib import Path
import pytest
import requests

NAEBI_API_URL = "https://rf-vp.agate.ch/digiflux/naebi/2-0/naebiservice-backend/agronomiccropcategories"
PSMV_CSV_URL = "https://raw.githubusercontent.com/BLV-OSAV-USAV/PSMV-RDF/refs/heads/main/data/raw/Code.csv.gz"
LOG_DIR = Path("build/test")
LOG_FILENAME = "psmv_drift.log"

def write_drift_log(filename: str, lines: list):
    """Writes a formatted log file detailing the data drift."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / filename
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def get_local_naebi_data(graph):
    """Extracts local NAEBI crop data from the combined processed graph."""
    query = """
    PREFIX schema: <http://schema.org/>
    PREFIX : <https://agriculture.ld.admin.ch/crops/>
    
    SELECT ?id ?name ?n2 ?p2o5 ?k2o ?mg
    WHERE {
        ?crop a :NutrientBalanceCrop ;
              schema:identifier ?id ;
              schema:name ?name .
              
        OPTIONAL { ?crop :N2 ?n2 . }
        OPTIONAL { ?crop :P2O5 ?p2o5 . }
        OPTIONAL { ?crop :K2O ?k2o . }
        OPTIONAL { ?crop :Mg ?mg . }
        
        FILTER(LANG(?name) = "de")
    }
    """
    results = graph.query(query)
    
    return {
        str(row.id): {
            "name": str(row.name),
            "N2": float(row.n2) if row.n2 is not None else 0.0,
            "P2O5": float(row.p2o5) if row.p2o5 is not None else 0.0,
            "K2O": float(row.k2o) if row.k2o is not None else 0.0,
            "Mg": float(row.mg) if row.mg is not None else 0.0
        } for row in results
    }

def get_api_naebi_data():
    """Fetches NAEBI crop data from the remote API."""
    response = requests.get(NAEBI_API_URL, timeout=15)
    response.raise_for_status()
    api_payload = response.json()
    
    api_data = {}
    for crop in api_payload:
        code = crop.get("code")
        reqs = {req["molecularFormula"]: float(req["quantity"]) for req in crop.get("requirement", [])}
        
        api_data[code] = {
            "name": crop.get("descriptor", {}).get("designation_deu", ""),
            "N2": reqs.get("N2", 0.0),
            "P2O5": reqs.get("P2O5", 0.0),
            "K2O": reqs.get("K2O", 0.0),
            "Mg": reqs.get("Mg", 0.0)
        }
    return api_data

def test_naebi_drift(final_graph):
    """Monitors discrepancies between local NAEBI RDF representations and the live Agate API."""
    local_data = get_local_naebi_data(final_graph)
    
    try:
        api_data = get_api_naebi_data()
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Network dependency unreachable. Skipping test. Error: {e}")

    local_keys = set(local_data.keys())
    api_keys = set(api_data.keys())

    new_in_api = api_keys - local_keys
    missing_in_api = local_keys - api_keys
    common_keys = local_keys.intersection(api_keys)

    discrepancies = {}

    for key in common_keys:
        local_crop = local_data[key]
        api_crop = api_data[key]
        diffs = []
        
        if local_crop["name"] != api_crop["name"]:
            diffs.append(f"Name: '{local_crop['name']}' -> '{api_crop['name']}'")
            
        for nut in ["N2", "P2O5", "K2O", "Mg"]:
            if local_crop[nut] != api_crop[nut]:
                diffs.append(f"{nut}: {local_crop[nut]} -> {api_crop[nut]}")
                
        if diffs:
            discrepancies[key] = diffs

    has_drift = new_in_api or missing_in_api or discrepancies

    if not has_drift:
        return

    log_lines = ["NAEBI DATA DRIFT REPORT", "=" * 23, ""]

    if new_in_api:
        log_lines.append(f"New Crops on API ({len(new_in_api)}):")
        for key in sorted(new_in_api):
            log_lines.append(f"  - {key}: {api_data[key]['name']}")
        log_lines.append("")

    if missing_in_api:
        log_lines.append(f"Crops Removed From API ({len(missing_in_api)}):")
        for key in sorted(missing_in_api):
            log_lines.append(f"  - {key}: {local_data[key]['name']}")
        log_lines.append("")

    if discrepancies:
        log_lines.append(f"Modified Data ({len(discrepancies)}):")
        for key, diffs in discrepancies.items():
            log_lines.append(f"  {key} ({local_data[key]['name']}):")
            for diff in diffs:
                log_lines.append(f"    - {diff}")
        log_lines.append("")

    write_drift_log("naebi_drift.log", log_lines)
    warnings.warn(
        "NAEBI data drift detected. See build/test/naebi_drift.log for details.",
        UserWarning
    )

def test_psmv_drift(final_graph):
    """
    Tests that the hierarchy and localized names in the remote PSMV CSV 
    match the local RDF representations.
    """
    try:
        response = requests.get(PSMV_CSV_URL, timeout=15)
        response.raise_for_status()
        csv_text = gzip.decompress(response.content).decode('utf-8')
        
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Network dependency unreachable. Skipping test. Error: {e}")
    except gzip.BadGzipFile:
        pytest.fail("Failed to decompress the remote file. The payload is not a valid GZIP archive.")

    csv_hierarchy = set()
    csv_names = set()
    
    reader = csv.DictReader(io.StringIO(csv_text))
    
    for row in reader:
        if row.get("TEXT_KEY") == "Culture":
            c_id = str(row.get("ID", "")).strip()
            c_parent_id = str(row.get("PARENT_ID", "")).strip()
            c_lang = str(row.get("LANGUAGE", "")).strip().lower()
            c_val = str(row.get("VALUE", "")).strip()
            
            if c_id and c_parent_id:
                csv_hierarchy.add((c_id, c_parent_id))
            if c_id and c_lang and c_val:
                csv_names.add((c_id, c_lang, c_val))
                
    if not csv_hierarchy and not csv_names:
        pytest.fail("The CSV filter returned 0 results. Check if the CSV structure changed.")

    rdf_hierarchy = set()
    rdf_names = set()

    sparql_query = """
    PREFIX schema: <http://schema.org/>
    PREFIX : <https://agriculture.ld.admin.ch/crops/>

    SELECT ?id ?parent_id ?name
    WHERE {
      ?obs a :PlantProtectionCrop ;
           schema:identifier ?id .
           
      OPTIONAL { ?obs schema:isPartOf / schema:identifier ?parent_id }
      OPTIONAL { ?obs schema:name ?name }
    }
    """
    
    for row in final_graph.query(sparql_query):
        r_id = str(row.id).strip()
        if row.parent_id:
            rdf_hierarchy.add((r_id, str(row.parent_id).strip()))
        if row.name:
            r_val = str(row.name).strip()
            r_lang = str(row.name.language).lower() if row.name.language else ""
            rdf_names.add((r_id, r_lang, r_val))

    missing_hierarchy = csv_hierarchy - rdf_hierarchy
    extra_hierarchy = rdf_hierarchy - csv_hierarchy
    missing_names = csv_names - rdf_names
    extra_names = rdf_names - csv_names
    
    has_drift = missing_hierarchy or extra_hierarchy or missing_names or extra_names

    if not has_drift:
        return

    log_lines = ["PSMV DATA DRIFT REPORT", "=" * 22, ""]

    if missing_hierarchy:
        log_lines.append(f"Missing Hierarchy in RDF ({len(missing_hierarchy)}):")
        for m_id, m_parent in sorted(list(missing_hierarchy)):
            log_lines.append(f"  - ID: {m_id} | Parent ID: {m_parent}")
        log_lines.append("")

    if extra_hierarchy:
        log_lines.append(f"Extra Hierarchy in RDF ({len(extra_hierarchy)}):")
        for e_id, e_parent in sorted(list(extra_hierarchy)):
            log_lines.append(f"  - ID: {e_id} | Parent ID: {e_parent}")
        log_lines.append("")

    if missing_names:
        log_lines.append(f"Missing Names in RDF ({len(missing_names)}):")
        for m_id, m_lang, m_val in sorted(list(missing_names)):
            log_lines.append(f"  - ID: {m_id} | Lang: {m_lang} | Value: {m_val}")
        log_lines.append("")

    if extra_names:
        log_lines.append(f"Extra Names in RDF ({len(extra_names)}):")
        for e_id, e_lang, e_val in sorted(list(extra_names)):
            log_lines.append(f"  - ID: {e_id} | Lang: {e_lang} | Value: {e_val}")
        log_lines.append("")

    write_drift_log(LOG_FILENAME, log_lines)
    warnings.warn(
        f"PSMV data drift detected. See {LOG_DIR}/{LOG_FILENAME} for details.", 
        UserWarning
    )