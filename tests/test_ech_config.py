"""
Validity of docs/_ech.yml, the eCH metadata shared by all language versions
of the documentation, against the codes of docs/assets/ech_vocabulary.yml.
"""
import datetime
import re
from pathlib import Path

import pytest
import yaml

ECH_CONFIG = Path("docs/_ech.yml")
VOCABULARY = Path("docs/assets/ech_vocabulary.yml")
QUARTO_CONFIG = Path("docs/_quarto.yml")

REQUIRED_KEYS = {"number", "category", "maturity", "version", "status", "languages", "group", "graph"}
OPTIONAL_KEYS = {"decision-date", "replaces", "prerequisites", "attachments", "publisher"}
CODE_GROUPS = {"category": "category", "maturity": "maturity", "status": "status"}
STATUSES_WITH_DECISION = {"approved", "replaced"}

ECH_NUMBER = re.compile(r"eCH-\d{4}")
SEMVER = re.compile(r"\d+\.\d+\.\d+")


@pytest.fixture(scope="module")
def config():
    if not ECH_CONFIG.exists():
        pytest.skip(f"{ECH_CONFIG} not found")
    data = yaml.safe_load(ECH_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{ECH_CONFIG} must be a YAML mapping"
    return data


@pytest.fixture(scope="module")
def ech(config):
    assert isinstance(config.get("ech"), dict), f"{ECH_CONFIG} needs an 'ech' mapping"
    return config["ech"]


@pytest.fixture(scope="module")
def vocabulary():
    if not VOCABULARY.exists():
        pytest.skip(f"{VOCABULARY} not found")
    return yaml.safe_load(VOCABULARY.read_text(encoding="utf-8"))


def codes(vocabulary, group):
    """The codes of a vocabulary group, taken from the first language."""
    first = next(iter(vocabulary.values()))
    return set(first[group])


def doc_languages():
    """The languages rendered by Quarto (docs/{lang}/index.qmd in project.render)."""
    quarto = yaml.safe_load(QUARTO_CONFIG.read_text(encoding="utf-8"))
    return {Path(p).parts[0] for p in quarto.get("project", {}).get("render", [])}


def test_vocabulary_is_consistent_across_languages(vocabulary):
    """Every language of the vocabulary defines the same keys and codes."""
    languages = list(vocabulary)
    reference = vocabulary[languages[0]]
    for lang in languages[1:]:
        assert set(vocabulary[lang]) == set(reference), f"vocabulary keys of '{lang}' differ from '{languages[0]}'"
        for group in ("labels", "category", "maturity", "status", "status-description", "change", "language"):
            assert set(vocabulary[lang][group]) == set(reference[group]), (
                f"'{group}' codes of '{lang}' differ from '{languages[0]}'"
            )


def test_keys(ech):
    """All required keys exist and no unknown key is present (typos would be ignored silently)."""
    missing = REQUIRED_KEYS - set(ech)
    unknown = set(ech) - REQUIRED_KEYS - OPTIONAL_KEYS
    assert not missing, f"missing keys under 'ech': {sorted(missing)}"
    assert not unknown, f"unknown keys under 'ech': {sorted(unknown)} (allowed: {sorted(REQUIRED_KEYS | OPTIONAL_KEYS)})"


def test_dates(config, ech):
    """The date of issue is a date; the decision date is a date or null, and set for approved documents."""
    assert isinstance(config.get("date"), datetime.date), "'date' (date of issue) must be an ISO date, e.g. 2026-10-01"
    decision = ech.get("decision-date")
    assert decision is None or isinstance(decision, datetime.date), "'decision-date' must be an ISO date or null"
    if ech.get("status") in STATUSES_WITH_DECISION:
        assert decision is not None, f"status '{ech['status']}' requires a 'decision-date'"
    if decision is not None:
        assert decision <= config["date"], "'decision-date' must not be after the date of issue"


def test_number_and_version(ech):
    assert ECH_NUMBER.fullmatch(str(ech["number"])), f"'number' must look like eCH-0000, got {ech['number']!r}"
    assert SEMVER.fullmatch(str(ech["version"])), f"'version' must be a semantic version (e.g. 2.4.1), got {ech['version']!r}"


@pytest.mark.parametrize("field", sorted(CODE_GROUPS))
def test_codes(ech, vocabulary, field):
    """category, maturity and status are codes of the vocabulary."""
    allowed = codes(vocabulary, CODE_GROUPS[field])
    assert ech[field] in allowed, f"'{field}' is {ech[field]!r}, allowed: {sorted(allowed)}"


def test_replaces(ech, vocabulary):
    """'replaces' is null (first version) or gives the replaced version and the kind of change."""
    replaces = ech.get("replaces")
    if replaces is None:
        return
    assert isinstance(replaces, dict), "'replaces' must be a mapping with 'version' and 'change', or null"
    assert not set(replaces) - {"version", "change"}, f"unknown keys under 'replaces': {sorted(set(replaces) - {'version', 'change'})}"
    allowed = codes(vocabulary, "change")
    assert replaces.get("change") in allowed, f"'replaces.change' is {replaces.get('change')!r}, allowed: {sorted(allowed)}"
    if replaces["change"] != "new":
        assert SEMVER.fullmatch(str(replaces.get("version", ""))), "'replaces.version' must be a semantic version"
        assert str(replaces["version"]) != str(ech["version"]), "'replaces.version' must differ from 'version'"


def test_lists(ech):
    """prerequisites and attachments are lists of strings; prerequisites are eCH numbers."""
    for key in ("prerequisites", "attachments"):
        value = ech.get(key, [])
        assert isinstance(value, list) and all(isinstance(v, str) for v in value), f"'{key}' must be a list of strings"
    bad = [p for p in ech.get("prerequisites", []) if not ECH_NUMBER.match(p)]
    assert not bad, f"'prerequisites' must name eCH standards (eCH-0000 ...), got {bad}"


def test_languages(ech, vocabulary):
    """The original language and its translations are known codes and match the rendered languages."""
    languages = ech["languages"]
    assert isinstance(languages, dict) and "original" in languages, "'languages' needs 'original' (and optionally 'translations')"
    original = languages["original"]
    translations = languages.get("translations") or []
    allowed = codes(vocabulary, "language")
    assert original in allowed, f"'languages.original' is {original!r}, allowed: {sorted(allowed)}"
    assert isinstance(translations, list) and set(translations) <= allowed, f"'languages.translations' must be a list of {sorted(allowed)}"
    assert original not in translations, "the original language is not a translation"
    assert len(translations) == len(set(translations)), "'languages.translations' has duplicates"
    assert {original, *translations} == doc_languages(), (
        f"languages {sorted({original, *translations})} differ from the rendered ones {sorted(doc_languages())} (project.render in docs/_quarto.yml)"
    )


def test_group_and_graph(ech):
    assert isinstance(ech["group"], str) and ech["group"].strip(), "'group' (Fachgruppe) must be a non-empty string"
    graph = str(ech["graph"])
    assert re.fullmatch(r"https://\S+", graph), f"'graph' must be an https IRI of the named graph on LINDAS, got {graph!r}"
