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
"""

import csv
import gzip
import io
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
    """Fetches a remote source, skipping the test if the source is unreachable."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        pytest.skip(f"Source {url} is unreachable. Error: {error}")
    return response

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
