import pytest
import requests
import csv
import io
import gzip
from rdflib.graph import ReadOnlyGraphAggregate

CSV_URL = "https://raw.githubusercontent.com/BLV-OSAV-USAV/PSMV-RDF/refs/heads/main/data/raw/Code.csv.gz"

@pytest.mark.drift
def test_psmv_drift(srppp_graph, core_graph):
    """
    Tests that the hierarchy and localized names in the remote CSV 
    EXACTLY MATCH the local RDF graphs.
    """
    try:
        response = requests.get(CSV_URL, timeout=15)
        response.raise_for_status()
        
        csv_text = gzip.decompress(response.content).decode('utf-8')
        
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Network dependency unreachable. Skipping test. Error: {e}")
    except gzip.BadGzipFile:
        pytest.fail("Failed to decompress the remote file. The payload is not a valid GZIP archive.")

    csv_hierarchy = set()
    csv_names = set()
    
    # Pass the decompressed string into the CSV reader
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

    combined_graph = ReadOnlyGraphAggregate([srppp_graph, core_graph])

    rdf_hierarchy = set()
    rdf_names = set()

    sparql_combined = """
    PREFIX cube: <https://cube.link/>
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?id ?parent_id ?name
    WHERE {
      ?obs a/rdfs:subClassOf* cube:Observation ;
           schema:identifier ?id .
           
      OPTIONAL { ?obs schema:isPartOf / schema:identifier ?parent_id }
      OPTIONAL { ?obs schema:name ?name }
    }
    """
    for row in combined_graph.query(sparql_combined):
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
        return # Test passes silently

    # Build Markdown Report
    md_lines = [
        "Automated monitoring has detected a drift between the local PSMV RDF graphs and the remote PSMV CSV.\n"
    ]

    if missing_hierarchy:
        md_lines.append(f"### ⚠️ Missing Hierarchy in RDF ({len(missing_hierarchy)})")
        md_lines.append("Found in CSV, not in RDF:")
        for m_id, m_parent in list(missing_hierarchy)[:10]:
            md_lines.append(f"- **ID:** `{m_id}` | **Parent ID:** `{m_parent}`")
        if len(missing_hierarchy) > 10: md_lines.append(f"- *...and {len(missing_hierarchy) - 10} more.*")
        md_lines.append("")

    if extra_hierarchy:
        md_lines.append(f"### 🗑️ Extra Hierarchy in RDF ({len(extra_hierarchy)})")
        md_lines.append("Found in RDF, not in CSV:")
        for e_id, e_parent in list(extra_hierarchy)[:10]:
            md_lines.append(f"- **ID:** `{e_id}` | **Parent ID:** `{e_parent}`")
        if len(extra_hierarchy) > 10: md_lines.append(f"- *...and {len(extra_hierarchy) - 10} more.*")
        md_lines.append("")

    if missing_names:
        md_lines.append(f"### 📝 Missing Names in RDF ({len(missing_names)})")
        md_lines.append("Found in CSV, not in RDF:")
        for m_id, m_lang, m_val in list(missing_names)[:10]:
            md_lines.append(f"- **ID:** `{m_id}` | **Lang:** `{m_lang}` | **Value:** `{m_val}`")
        if len(missing_names) > 10: md_lines.append(f"- *...and {len(missing_names) - 10} more.*")
        md_lines.append("")

    if extra_names:
        md_lines.append(f"### 🗑️ Extra Names in RDF ({len(extra_names)})")
        md_lines.append("Found in RDF, not in CSV:")
        for e_id, e_lang, e_val in list(extra_names)[:10]:
            md_lines.append(f"- **ID:** `{e_id}` | **Lang:** `{e_lang}` | **Value:** `{e_val}`")
        if len(extra_names) > 10: md_lines.append(f"- *...and {len(extra_names) - 10} more.*")
        md_lines.append("")

    report_md = "\n".join(md_lines)
    
    with open("psmv_drift_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    
    pytest.fail(f"PSMV Data Drift Detected:\n\n{report_md}")