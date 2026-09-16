"""Data drift tests.

The RDF data in ``src/rdf/data`` is a curated copy of crop code lists that are
maintained in other systems. These tests compare the processed graph against
those upstream sources and fail as soon as the sources start to drift away from
what this repository publishes.

For every code list the same three questions are asked:

1. Are exactly the same crops represented (no more, no less)?
2. Are all available names identical?
3. Is the hierarchy (categories, broader concepts) represented correctly?

Whenever a test fails, a human readable report is written to ``build/test`` so
that the concrete differences can be inspected without re-running the test.

The tests depend on remote sources, and the two ways of losing a source are
told apart deliberately. A client error (HTTP 4xx) will trigger an error, a
server error (HTTP 5xx) or an unreachable host is a will skip the test.
"""

import csv
import gzip
import io
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import pytest
import requests

# ==============================================================================
# SOURCES
# ==============================================================================

NAEBI_BASE_URL = "https://rf-vp.agate.ch/digiflux/naebi/2-0/naebiservice-backend"
NAEBI_CROPS_URL = f"{NAEBI_BASE_URL}/agronomiccropcategories"
NAEBI_CATEGORIES_URL = f"{NAEBI_BASE_URL}/cultivationcategories"
NAEBI_SUBCATEGORIES_URL = f"{NAEBI_BASE_URL}/cultivationsubcategories"
PSM_CSV_URL = "https://raw.githubusercontent.com/BLV-OSAV-USAV/PSMV-RDF/refs/heads/main/data/raw/Code.csv.gz"
GIS_XML_URL = "https://models.geo.admin.ch/BLW/LWB_Nutzungsflaechen_Kataloge_V3_0.xml"

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2

# The NAEBI API returns one designation per language, the PSM code list uses
# BCP-47 language tags directly and the INTERLIS catalogue uses ISO 639-2 codes.
NAEBI_DESIGNATIONS = {
    "designation_deu": "de",
    "designation_eng": "en",
    "designation_fra": "fr",
    "designation_ita": "it",
}
GIS_LANGUAGES = {"de": "de", "fr": "fr", "it": "it"}

INTERLIS_NS = {"ili": "http://www.interlis.ch/INTERLIS2.3"}
INTERLIS_CROP_TAG = "ili:LWB_Nutzungsflaechen_V3_0.LNF_Kataloge.LNF_Katalog_Nutzungsart"

LOG_DIR = Path("build/test")
PSMV_LOG_FILENAME = "psmv_drift.log"
NAEBI_LOG_FILENAME = "naebi_drift.log"
GIS_LOG_FILENAME = "gis_drift.log"
MGDM_LOG_FILENAME = "mgdm_drift.log"

PREFIXES = """
PREFIX ech: <https://agriculture.ld.admin.ch/eCH-0265/2/>
PREFIX schema: <http://schema.org/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

# ==============================================================================
# REPORTING HELPERS
# ==============================================================================

def write_drift_log(filename, title, sections):
    """Writes a formatted log file detailing the data drift."""
    lines = [title, "=" * len(title), ""]
    for heading, entries in sections:
        lines.append(f"{heading} ({len(entries)}):")
        lines.extend(entries)
        lines.append("")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / filename
    log_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return log_path

def assert_no_drift(filename, title, sections):
    """Fails the test if any of the given report sections is non-empty."""
    sections = [(heading, entries) for heading, entries in sections if entries]
    if not sections:
        return
    log_path = write_drift_log(filename, title, sections)
    summary = ", ".join(f"{heading.lower()}: {len(entries)}" for heading, entries in sections)
    pytest.fail(f"{title} ({summary}). See {log_path} for details.")

def set_drift(local, source, describe_local, describe_source):
    """Builds the report sections for the symmetric difference of two key sets."""
    return [
        (
            "Present in the source but missing locally",
            [f"  - {key}: {describe_source(key)}" for key in sorted(source - local)],
        ),
        (
            "Present locally but missing in the source",
            [f"  - {key}: {describe_local(key)}" for key in sorted(local - source)],
        ),
    ]

def name_drift(local, source, languages):
    """Compares two ``{key: {language: name}}`` mappings for the given languages."""
    entries = []
    for key in sorted(set(local) & set(source)):
        for language in languages:
            local_name = local[key].get(language)
            source_name = source[key].get(language)
            if local_name != source_name:
                entries.append(
                    f"  - {key} [{language}]: local {local_name!r} != source {source_name!r}"
                )
    return [("Diverging names", entries)]

def value_drift(local, source, label):
    """Compares two ``{key: set(value)}`` mappings entry by entry."""
    entries = []
    for key in sorted(set(local) & set(source)):
        if local[key] != source[key]:
            entries.append(
                f"  - {key}: local {sorted(local[key])} != source {sorted(source[key])}"
            )
    return [(f"Diverging {label}", entries)]

# ==============================================================================
# GRAPH HELPERS
# ==============================================================================

def localised_names(graph, query):
    """Returns ``{identifier: {language: name}}`` for a query binding ?id and ?name."""
    names = defaultdict(dict)
    for row in graph.query(PREFIXES + query):
        entry = names[str(row.id)]
        if row.name is not None:
            entry[row.name.language or ""] = str(row.name)
    return dict(names)

def grouped_values(graph, query, variable):
    """Returns ``{identifier: set(value)}`` for a query binding ?id and the variable."""
    values = defaultdict(set)
    for row in graph.query(PREFIXES + query):
        # Concepts without any value have to stay in the mapping, otherwise a
        # missing value would silently be excluded from the comparison.
        entry = values[str(row.id)]
        value = getattr(row, variable)
        if value is not None:
            entry.add(str(value))
    return dict(values)

def duplicate_identifiers(graph, query):
    """Returns report entries for identifiers that are shared by several concepts."""
    concepts = defaultdict(set)
    for row in graph.query(PREFIXES + query):
        concepts[str(row.id)].add(str(row.concept))
    return [
        f"  - {identifier}: {', '.join(sorted(uris))}"
        for identifier, uris in sorted(concepts.items())
        if len(uris) > 1
    ]

# ==============================================================================
# SOURCE FIXTURES
# ==============================================================================

def fetch(url):
    """Fetches a remote source, retrying and skipping only on temporary outages.

    The tests depend on remote sources, and the two ways of losing a source are
    told apart deliberately. A client error (HTTP 4xx) means the source itself
    moved or disappeared. That never recovers on its own and has to be fixed
    here, so the test errors out instead of quietly disappearing from the
    report. A server error (HTTP 5xx) or an unreachable host is a temporary
    outage on the other side: the request is retried and the test is skipped if
    the source stays unavailable.
    """
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as error:
            last_error = error
        else:
            if response.status_code < 400:
                return response
            if response.status_code < 500:
                pytest.fail(
                    f"HTTP {response.status_code} for {url}. The source has moved or "
                    f"disappeared, so this test has to be pointed at its new location."
                )
            last_error = f"HTTP {response.status_code} {response.reason}"

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    pytest.skip(
        f"Source {url} did not respond after {MAX_RETRIES} attempts. "
        f"Reason: {last_error}"
    )

def designations(payload):
    """Maps the ``descriptor`` of a NAEBI API entry to language tagged names."""
    descriptor = payload.get("descriptor", {})
    return {
        language: descriptor[field]
        for field, language in NAEBI_DESIGNATIONS.items()
        if descriptor.get(field)
    }

@pytest.fixture(scope="session")
def naebi_api_crops():
    """``{code: entry}`` of all nutrient balance crops known to the NAEBI API."""
    return {crop["code"]: crop for crop in fetch(NAEBI_CROPS_URL).json()}

@pytest.fixture(scope="session")
def naebi_api_categories():
    """``{code: {language: name}}`` of the NAEBI cultivation categories."""
    payload = fetch(NAEBI_CATEGORIES_URL).json()
    return {entry["cultivationCategory"]: designations(entry) for entry in payload}

@pytest.fixture(scope="session")
def naebi_api_subcategories():
    """``{code: {language: name}}`` of the NAEBI cultivation subcategories."""
    payload = fetch(NAEBI_SUBCATEGORIES_URL).json()
    return {entry["code"]: designations(entry) for entry in payload}

@pytest.fixture(scope="session")
def psm_source():
    """Parses the published PSM code list into names and broader concepts."""
    response = fetch(PSM_CSV_URL)
    try:
        text = gzip.decompress(response.content).decode("utf-8")
    except gzip.BadGzipFile:
        pytest.fail(f"The payload of {PSM_CSV_URL} is not a valid GZIP archive.")

    names = {}
    parents = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row.get("TEXT_KEY") != "Culture":
            continue
        identifier = (row.get("ID") or "").strip()
        if not identifier:
            continue
        crop_names = names.setdefault(identifier, {})
        crop_parents = parents.setdefault(identifier, set())
        language = (row.get("LANGUAGE") or "").strip().lower()
        value = (row.get("VALUE") or "").strip()
        if language and value:
            crop_names[language] = value
        parent = (row.get("PARENT_ID") or "").strip()
        if parent:
            crop_parents.add(parent)

    if not names:
        pytest.fail(f"No 'Culture' entries found in {PSM_CSV_URL}. Did the format change?")
    return {"names": names, "parents": parents}

@pytest.fixture(scope="session")
def gis_source():
    """Parses the INTERLIS catalogue of direct payment crops into localised names."""
    response = fetch(GIS_XML_URL)
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as error:
        pytest.fail(f"Failed to parse XML from {GIS_XML_URL}. Error: {error}")

    crops = {}
    for crop in root.findall(f".//{INTERLIS_CROP_TAG}", INTERLIS_NS):
        code = (crop.findtext("ili:LNF_Code", "", INTERLIS_NS) or "").strip()
        if not code:
            continue
        names = {}
        for text in crop.findall(".//ili:Nutzung//ili:LocalisationCH_V1.LocalisedText", INTERLIS_NS):
            language = (text.findtext("ili:Language", "", INTERLIS_NS) or "").strip().lower()
            value = (text.findtext("ili:Text", "", INTERLIS_NS) or "").strip()
            if language in GIS_LANGUAGES and value:
                names[GIS_LANGUAGES[language]] = value
        crops[code] = names

    if not crops:
        pytest.fail(f"No crop entries found in {GIS_XML_URL}. Did the format change?")
    return crops

# ==============================================================================
# LOCAL FIXTURES
# ==============================================================================

@pytest.fixture(scope="session")
def naebi_local_names(final_graph):
    return localised_names(final_graph, """
        SELECT ?id ?name WHERE {
            ?crop a ech:NutrientBalanceCrop ;
                schema:identifier ?id .
            OPTIONAL { ?crop schema:name ?name }
        }
    """)

@pytest.fixture(scope="session")
def psm_local_names(final_graph):
    return localised_names(final_graph, """
        SELECT ?id ?name WHERE {
            ?crop a ech:PlantProtectionCrop ;
                schema:identifier ?id .
            OPTIONAL { ?crop schema:name ?name }
        }
    """)

@pytest.fixture(scope="session")
def agis_local_names(final_graph):
    return localised_names(final_graph, """
        SELECT ?id ?name WHERE {
            ?crop a ech:DirectPaymentCrop ;
                schema:identifier ?id .
            OPTIONAL { ?crop schema:name ?name }
        }
    """)

# ==============================================================================
# NUTRIENT BALANCE CROPS (NAEBI)
# ==============================================================================

def test_naebi_crops_match_api(naebi_local_names, naebi_api_crops):
    """Exactly the crops of the NAEBI API are represented -- no more, no less."""
    assert_no_drift(
        "naebi_crops.log",
        "NAEBI crop drift report",
        set_drift(
            set(naebi_local_names),
            set(naebi_api_crops),
            lambda key: naebi_local_names[key].get("de", "no German name"),
            lambda key: designations(naebi_api_crops[key]).get("de", "no German name"),
        ),
    )

def test_naebi_crop_names_match_api(naebi_local_names, naebi_api_crops):
    """The German crop names are identical to the designations of the NAEBI API.

    Only German is compared because the API does not provide any translations
    yet; ``test_naebi_api_provides_no_translations`` guards that assumption.
    """
    source = {code: designations(crop) for code, crop in naebi_api_crops.items()}
    assert_no_drift(
        "naebi_crop_names.log",
        "NAEBI crop name drift report",
        name_drift(naebi_local_names, source, ["de"]),
    )

def test_naebi_api_provides_no_translations(naebi_api_crops):
    """The NAEBI API repeats the German designation for every other language.

    As soon as the API starts to deliver real translations, this test fails and
    the name comparison above has to be extended to those languages.
    """
    entries = []
    for code, crop in sorted(naebi_api_crops.items()):
        names = designations(crop)
        translated = {
            language: name
            for language, name in names.items()
            if language != "de" and name != names.get("de")
        }
        if translated:
            entries.append(f"  - {code}: {translated}")
    assert_no_drift(
        "naebi_translations.log",
        "NAEBI translation availability report",
        [("Crops with translated designations", entries)],
    )

def test_naebi_categories_match_api(final_graph, naebi_api_categories, naebi_api_subcategories):
    """The cultivation (sub)categories and their names match the NAEBI API."""
    category_query = """
        SELECT ?concept ?id ?name WHERE {
            ?concept a ech:NutrientBalanceCropCategory ;
                schema:identifier ?id .
            OPTIONAL { ?concept schema:name ?name }
        }
    """
    subcategory_query = """
        SELECT ?concept ?id ?name WHERE {
            ?concept a ech:NutrientBalanceCropSubCategory ;
                schema:identifier ?id .
            OPTIONAL { ?concept schema:name ?name }
        }
    """
    results = graph.query(query)
    
    agis_data = {}
    for row in results:
        code = str(row.id)
        name = str(row.name)
        lang = str(row.lang).lower()
        
        if code not in agis_data:
            agis_data[code] = {}
        agis_data[code][lang] = name
        
    return agis_data

def get_api_agis_data():
    """Fetches AGIS crop data from the remote INTERLIS XML."""
    response = requests.get(GIS_XML_URL, timeout=15)
    response.raise_for_status()
    root = ET.fromstring(response.content)    
    ns = {'ili': 'http://www.interlis.ch/INTERLIS2.3'}
    
    api_data = {}
    for nutzungsart in root.findall(".//ili:LWB_Nutzungsflaechen_V3_0.LNF_Kataloge.LNF_Katalog_Nutzungsart", ns):
        code_elem = nutzungsart.find("ili:LNF_Code", ns)
        if code_elem is not None and code_elem.text:
            code = code_elem.text.strip()
            
            names = {}
            nutzung = nutzungsart.find("ili:Nutzung", ns)
            if nutzung is not None:
                for loc_text in nutzung.findall(".//ili:LocalisationCH_V1.LocalisedText", ns):
                    lang_elem = loc_text.find("ili:Language", ns)
                    text_elem = loc_text.find("ili:Text", ns)
                    if lang_elem is not None and text_elem is not None:
                        lang = lang_elem.text.strip().lower()
                        text = text_elem.text.strip() if text_elem.text else ""
                        names[lang] = text
                        
            api_data[code] = names
            
    return api_data

@pytest.mark.xfail(reason="Direct payments crops are currently not the same as GIS crops, although they should be!")
def test_agis_drift(final_graph):
    """Monitors discrepancies between local AGIS RDF representations and the live INTERLIS XML."""
    local_data = get_local_agis_data(final_graph)
    
    try:
        api_data = get_api_agis_data()
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Network dependency unreachable. Skipping test. Error: {e}")
    except ET.ParseError as e:
        pytest.fail(f"Failed to parse XML from {GIS_XML_URL}. Error: {e}")

    local_keys = set(local_data.keys())
    api_keys = set(api_data.keys())

    new_in_api = api_keys - local_keys
    missing_in_api = local_keys - api_keys
    common_keys = local_keys.intersection(api_keys)

    discrepancies = {}

    for key in common_keys:
        local_names = local_data[key]
        api_names = api_data[key]
        
        diffs = []
        # Check specific language components
        for lang in ['de', 'fr', 'it']:
            local_name = local_names.get(lang, "")
            api_name = api_names.get(lang, "")
            if local_name != api_name:
                if not local_name and api_name:
                    diffs.append(f"Missing {lang.upper()} name in local: API has '{api_name}'")
                elif local_name and not api_name:
                    diffs.append(f"Extra {lang.upper()} name in local: API has no name, local has '{local_name}'")
                else:
                    diffs.append(f"{lang.upper()} Name: '{local_name}' -> '{api_name}'")
                    
        if diffs:
            discrepancies[key] = diffs

    has_drift = bool(new_in_api or missing_in_api or discrepancies)

    if has_drift:
        log_lines = ["AGIS DATA DRIFT REPORT", "=" * 22, ""]

        if new_in_api:
            log_lines.append(f"New Crops on API ({len(new_in_api)}):")
            for key in sorted(new_in_api):
                log_lines.append(f"  - {key}: {api_data[key].get('de', 'No DE name')}")
            log_lines.append("")

        if missing_in_api:
            log_lines.append(f"Crops Removed From API ({len(missing_in_api)}):")
            for key in sorted(missing_in_api):
                log_lines.append(f"  - {key}: {local_data[key].get('de', 'No DE name')}")
            log_lines.append("")

        if discrepancies:
            log_lines.append(f"Modified Data ({len(discrepancies)}):")
            for key, diffs in discrepancies.items():
                log_lines.append(f"  {key} ({local_data[key].get('de', 'No DE name')}):")
                for diff in diffs:
                    log_lines.append(f"    - {diff}")
            log_lines.append("")

        write_drift_log(GIS_LOG_FILENAME, log_lines)

    assert not has_drift, f"AGIS data drift detected. See {LOG_DIR}/{GIS_LOG_FILENAME} for details."

def get_local_mgdm_data(graph):
    """Extracts local geodata crop (MGDM 153.1) data from the combined processed graph."""
    query = """
    PREFIX schema: <http://schema.org/>
    PREFIX eCH-0265: <https://agriculture.ld.admin.ch/eCH-0265/2/>

    SELECT ?id ?name ?validFrom ?validTo ?overlapping ?bff ?special
    WHERE {
        ?crop a eCH-0265:GeodataCrop ;
              schema:identifier ?id ;
              schema:name ?name ;
              eCH-0265:overlapping ?overlapping ;
              eCH-0265:biodiversityPromotionAreaQualityLevelOne ?bff ;
              eCH-0265:specialCrop ?special .
        OPTIONAL { ?crop schema:validFrom ?validFrom . }
        OPTIONAL { ?crop schema:validTo ?validTo . }
    }
    """
    local_data = {}
    for row in graph.query(query):
        code = str(row.id)
        entry = local_data.setdefault(code, {
            "names": {},
            "validFrom": str(row.validFrom) if row.validFrom is not None else None,
            "validTo": str(row.validTo) if row.validTo is not None else None,
            "overlapping": str(bool(row.overlapping)).lower(),
            "bff": str(bool(row.bff)).lower(),
            "special": str(bool(row.special)).lower(),
        })
        entry["names"][str(row.name.language).lower()] = str(row.name).strip()
    return local_data

def get_api_mgdm_data():
    """Fetches the LNF_Katalog_Nutzungsart entries from the remote INTERLIS XML."""
    response = requests.get(GIS_XML_URL, timeout=15)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    ns = {'ili': 'http://www.interlis.ch/INTERLIS2.3'}

    def text(elem, tag):
        child = elem.find(f"ili:{tag}", ns)
        return child.text.strip() if child is not None and child.text else None

    api_data = {}
    for nutzungsart in root.findall(".//ili:LWB_Nutzungsflaechen_V3_0.LNF_Kataloge.LNF_Katalog_Nutzungsart", ns):
        code = text(nutzungsart, "LNF_Code")
        if not code:
            continue
        names = {}
        nutzung = nutzungsart.find("ili:Nutzung", ns)
        if nutzung is not None:
            for loc_text in nutzung.findall(".//ili:LocalisationCH_V1.LocalisedText", ns):
                lang = text(loc_text, "Language")
                value = text(loc_text, "Text")
                if lang and value:
                    names[lang.lower()] = value
        api_data[code] = {
            "names": names,
            "validFrom": text(nutzungsart, "Gueltig_Von"),
            "validTo": text(nutzungsart, "Gueltig_Bis"),
            "overlapping": text(nutzungsart, "Ist_Ueberlagernd"),
            "bff": text(nutzungsart, "Ist_BFF_QI"),
            "special": text(nutzungsart, "Ist_Spezialkultur"),
        }
    return api_data

def test_mgdm_drift(final_graph):
    """Monitors discrepancies between the local geodata crops (MGDM 153.1) and the live INTERLIS XML catalogue."""
    local_data = get_local_mgdm_data(final_graph)

    try:
        api_data = get_api_mgdm_data()
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Network dependency unreachable. Skipping test. Error: {e}")
    except ET.ParseError as e:
        pytest.fail(f"Failed to parse XML from {GIS_XML_URL}. Error: {e}")

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

        for lang in ['de', 'fr', 'it']:
            local_name = local_crop["names"].get(lang, "")
            api_name = api_crop["names"].get(lang, "")
            if local_name != api_name:
                diffs.append(f"{lang.upper()} Name: '{local_name}' -> '{api_name}'")

        for attr in ["validFrom", "validTo", "overlapping", "bff", "special"]:
            if local_crop[attr] != api_crop[attr]:
                diffs.append(f"{attr}: {local_crop[attr]} -> {api_crop[attr]}")

        if diffs:
            discrepancies[key] = diffs

    has_drift = bool(new_in_api or missing_in_api or discrepancies)

    if has_drift:
        log_lines = ["MGDM DATA DRIFT REPORT", "=" * 22, ""]

        if new_in_api:
            log_lines.append(f"New Crops in Catalogue ({len(new_in_api)}):")
            for key in sorted(new_in_api):
                log_lines.append(f"  - {key}: {api_data[key]['names'].get('de', 'No DE name')}")
            log_lines.append("")

        if missing_in_api:
            log_lines.append(f"Crops Removed From Catalogue ({len(missing_in_api)}):")
            for key in sorted(missing_in_api):
                log_lines.append(f"  - {key}: {local_data[key]['names'].get('de', 'No DE name')}")
            log_lines.append("")

        if discrepancies:
            log_lines.append(f"Modified Data ({len(discrepancies)}):")
            for key, diffs in sorted(discrepancies.items()):
                log_lines.append(f"  {key} ({local_data[key]['names'].get('de', 'No DE name')}):")
                for diff in diffs:
                    log_lines.append(f"    - {diff}")
            log_lines.append("")

        write_drift_log(MGDM_LOG_FILENAME, log_lines)

    assert not has_drift, f"MGDM data drift detected. See {LOG_DIR}/{MGDM_LOG_FILENAME} for details."
    local_categories = localised_names(final_graph, category_query)
    local_subcategories = localised_names(final_graph, subcategory_query)

    sections = [("Ambiguous identifiers", duplicate_identifiers(final_graph, category_query)
                 + duplicate_identifiers(final_graph, subcategory_query))]
    for local, source in ((local_categories, naebi_api_categories),
                          (local_subcategories, naebi_api_subcategories)):
        sections += set_drift(
            set(local),
            set(source),
            lambda key, local=local: local[key].get("de", "no German name"),
            lambda key, source=source: source[key].get("de", "no German name"),
        )
        sections += name_drift(local, source, ["de"])

    assert_no_drift("naebi_categories.log", "NAEBI category drift report", sections)

def test_naebi_hierarchy_matches_api(final_graph, naebi_api_crops):
    """Every crop is assigned to the cultivation category and subcategory of the API."""
    local_categories = grouped_values(final_graph, """
        SELECT ?id ?category WHERE {
            ?crop a ech:NutrientBalanceCrop ;
                schema:identifier ?id .
            OPTIONAL { ?crop ech:cultivationCategory / schema:identifier ?category }
        }
    """, "category")
    local_subcategories = grouped_values(final_graph, """
        SELECT ?id ?subcategory WHERE {
            ?crop a ech:NutrientBalanceCrop ;
                schema:identifier ?id .
            OPTIONAL { ?crop ech:cultivationSubCategory / schema:identifier ?subcategory }
        }
    """, "subcategory")

    source_categories = {
        code: {crop["cultivationCategory"]} if crop.get("cultivationCategory") else set()
        for code, crop in naebi_api_crops.items()
    }
    source_subcategories = {
        code: {crop["cultivationSubCategory"]} if crop.get("cultivationSubCategory") else set()
        for code, crop in naebi_api_crops.items()
    }

    assert_no_drift(
        "naebi_hierarchy.log",
        "NAEBI hierarchy drift report",
        value_drift(local_categories, source_categories, "cultivation categories")
        + value_drift(local_subcategories, source_subcategories, "cultivation subcategories"),
    )

# ==============================================================================
# PLANT PROTECTION CROPS (PSM)
# ==============================================================================

def test_psm_crops_match_source(psm_local_names, psm_source):
    """Exactly the crops of the published PSM code list are represented."""
    source_names = psm_source["names"]
    assert_no_drift(
        "psm_crops.log",
        "PSM crop drift report",
        set_drift(
            set(psm_local_names),
            set(source_names),
            lambda key: psm_local_names[key].get("de", "no German name"),
            lambda key: source_names[key].get("de", "no German name"),
        ),
    )

def test_psm_crop_names_match_source(psm_local_names, psm_source):
    """All localised crop names are identical to the published PSM code list."""
    source_names = psm_source["names"]
    languages = sorted(
        {language for names in psm_local_names.values() for language in names}
        | {language for names in source_names.values() for language in names}
    )
    assert_no_drift(
        "psm_crop_names.log",
        "PSM crop name drift report",
        name_drift(psm_local_names, source_names, languages),
    )

def test_psm_hierarchy_matches_source(final_graph, psm_source):
    """Every crop has exactly the broader concepts of the published PSM code list."""
    local_parents = grouped_values(final_graph, """
        SELECT ?id ?parent WHERE {
            ?crop a ech:PlantProtectionCrop ;
                schema:identifier ?id .
            OPTIONAL { ?crop skos:broader / schema:identifier ?parent }
        }
    """, "parent")
    assert_no_drift(
        "psm_hierarchy.log",
        "PSM hierarchy drift report",
        value_drift(local_parents, psm_source["parents"], "broader concepts"),
    )

# ==============================================================================
# DIRECT PAYMENT CROPS (AGIS)
# ==============================================================================

@pytest.mark.xfail(reason="Direct payment crops are currently not the same as GIS crops, although they should be!")
def test_agis_crops_match_source(agis_local_names, gis_source):
    """Exactly the crops of the INTERLIS catalogue are represented."""
    assert_no_drift(
        "agis_crops.log",
        "AGIS crop drift report",
        set_drift(
            set(agis_local_names),
            set(gis_source),
            lambda key: agis_local_names[key].get("de", "no German name"),
            lambda key: gis_source[key].get("de", "no German name"),
        ),
    )

@pytest.mark.xfail(reason="Direct payment crops are currently not the same as GIS crops, although they should be!")
def test_agis_crop_names_match_source(agis_local_names, gis_source):
    """All localised crop names are identical to the INTERLIS catalogue."""
    assert_no_drift(
        "agis_crop_names.log",
        "AGIS crop name drift report",
        name_drift(agis_local_names, gis_source, sorted(set(GIS_LANGUAGES.values()))),
    )
