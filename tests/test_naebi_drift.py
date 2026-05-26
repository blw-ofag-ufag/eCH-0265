import requests
import pytest

API_URL = "https://rf-vp.agate.ch/digiflux/naebi/2-0/naebiservice-backend/agronomiccropcategories"

def get_local_data(g):
    """Extracts local crop data utilizing the injected naebi_graph fixture."""
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
    results = g.query(query)
    
    return {
        str(row.id): {
            "name": str(row.name),
            "N2": float(row.n2) if row.n2 is not None else 0.0,
            "P2O5": float(row.p2o5) if row.p2o5 is not None else 0.0,
            "K2O": float(row.k2o) if row.k2o is not None else 0.0,
            "Mg": float(row.mg) if row.mg is not None else 0.0
        } for row in results
    }

def get_api_data():
    response = requests.get(API_URL, timeout=15)
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

@pytest.mark.drift
def test_naebi_drift(naebi_graph):
    local_data = get_local_data(naebi_graph)
    
    try:
        api_data = get_api_data()
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
            diffs.append(f"**Name:** `{local_crop['name']}` → `{api_crop['name']}`")
            
        for nut in ["N2", "P2O5", "K2O", "Mg"]:
            if local_crop[nut] != api_crop[nut]:
                diffs.append(f"**{nut}:** `{local_crop[nut]}` → `{api_crop[nut]}`")
                
        if diffs:
            discrepancies[key] = diffs

    has_drift = new_in_api or missing_in_api or discrepancies

    if not has_drift:
        return # Test passes silently

    # Build Markdown Report
    md_lines = [
        "Automated monitoring has detected a drift between the local `naebi.ttl` and the live Agate API.\n"
    ]

    if new_in_api:
        md_lines.append(f"### ⚠️ New Crops on API ({len(new_in_api)})")
        for key in sorted(new_in_api):
            md_lines.append(f"- **{key}**: {api_data[key]['name']}")
        md_lines.append("")

    if missing_in_api:
        md_lines.append(f"### 🗑️ Crops Removed From API ({len(missing_in_api)})")
        for key in sorted(missing_in_api):
            md_lines.append(f"- **{key}**: {local_data[key]['name']}")
        md_lines.append("")

    if discrepancies:
        md_lines.append(f"### 🔄 Modified Data ({len(discrepancies)})")
        for key, diffs in discrepancies.items():
            md_lines.append(f"#### {key} ({local_data[key]['name']})")
            for diff in diffs:
                md_lines.append(f"- {diff}")
        md_lines.append("")

    report_md = "\n".join(md_lines)
    
    # write drift report
    with open("drift_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

    pytest.fail(f"NAEBI Data Drift Detected:\n\n{report_md}")