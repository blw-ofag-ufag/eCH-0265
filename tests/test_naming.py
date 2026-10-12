"""
Naming conventions of .github/CONTRIBUTING.md: file names, the project
namespace and the local names of RDF resources.

Violations are reported as warnings (one per convention), not as failures:
the conventions are recommendations, and renaming published resources is a
breaking change that has to be planned.
"""
import re
import subprocess
import warnings
from pathlib import Path

import pytest
import yaml
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH, SKOS

PREFIXES = Path("src/rdf/prefixes.ttl")
ECH_CONFIG = Path("docs/_ech.yml")
NAMESPACE_ROOT = "https://agriculture.ld.admin.ch/"

# Fixed by convention (GitHub, make) or by the tools that read them (Quarto
# recognises its template partials by name).
CONVENTIONAL_FILES = {"README.md", "LICENSE.md", "CLEANUP.md", "CONTRIBUTING.md", "Makefile",
                      "typst-template.typ", "typst-show.typ", "title-metadata.html"}
UPPERCASE_EXTENSIONS = {".R"}

SNAKE_CASE = re.compile(r"_?[a-z0-9]+(_[a-z0-9]+)*")  # Quarto config files start with "_"
PASCAL_CASE = re.compile(r"[A-Z][a-z0-9]*([A-Z][a-z0-9]*)*")
CAMEL_CASE = re.compile(r"[a-z][a-z0-9]*([A-Z][a-z0-9]*)*")
IDENTIFIER = re.compile(r"(?=.*[0-9])[a-z0-9][a-z0-9_-]*")  # e.g. person:1, invoice:2021-03, a hash
VERB_PREFIX = re.compile(r"(has|is)[A-Z]")
SUBNAMESPACE = re.compile(r"[a-z][a-z0-9_]*/")

MAX_EXAMPLES = 10


def report(title, items):
    """Emits one aggregated warning for a convention, with a few examples."""
    if not items:
        return
    items = sorted(items)
    shown = items[:MAX_EXAMPLES]
    more = f"\n  ... and {len(items) - MAX_EXAMPLES} more" if len(items) > MAX_EXAMPLES else ""
    warnings.warn(f"{title} ({len(items)}):\n  " + "\n  ".join(shown) + more, UserWarning)


def tracked_files():
    result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True)
    return [Path(f) for f in result.stdout.split("\0") if f]


def project_namespace():
    """The IRI of the empty prefix in src/rdf/prefixes.ttl (the project namespace)."""
    match = re.search(r"^@prefix\s+:\s*<([^>]+)>", PREFIXES.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


def declared_namespaces():
    """All prefix declarations of src/rdf/prefixes.ttl as {prefix: iri}."""
    return dict(re.findall(r"^@prefix\s+([^\s:]*):\s*<([^>]+)>", PREFIXES.read_text(encoding="utf-8"), re.M))


def ech_config():
    return yaml.safe_load(ECH_CONFIG.read_text(encoding="utf-8")) or {}


def qname_function():
    """Abbreviates IRIs with the prefixes of src/rdf/prefixes.ttl (longest namespace wins)."""
    namespaces = sorted(declared_namespaces().items(), key=lambda item: -len(item[1]))

    def qname(iri):
        for prefix, namespace in namespaces:
            if str(iri).startswith(namespace):
                return f"{prefix}:{str(iri)[len(namespace):]}"
        return f"<{iri}>"
    return qname


def test_file_names_are_snake_case():
    """All files are named in lowercase snake_case (CONTRIBUTING.md, "File naming convention")."""
    violations = []
    for path in tracked_files():
        if path.name in CONVENTIONAL_FILES or path.name.startswith("."):
            continue
        stem, *extensions = path.name.split(".")
        bad_extensions = [e for e in extensions if not (e.islower() and e.isalnum()) and "." + e not in UPPERCASE_EXTENSIONS]
        if not SNAKE_CASE.fullmatch(stem) or bad_extensions:
            violations.append(str(path))
    report("Files not named in lowercase snake_case", violations)


def test_project_namespace_follows_convention():
    """
    The project namespace is https://agriculture.ld.admin.ch/{eCH number}/{major version}/
    and its sub-namespaces add one lowercase segment (CONTRIBUTING.md, "RDF namespace naming convention").
    """
    if not PREFIXES.exists():
        pytest.skip(f"{PREFIXES} not found")
    base = project_namespace()
    ech = ech_config().get("ech", {})
    number, version = ech.get("number"), str(ech.get("version", ""))
    violations = []
    if not base:
        violations.append("src/rdf/prefixes.ttl declares no empty prefix ':' for the project namespace")
    elif number and version:
        expected = f"{NAMESPACE_ROOT}{number}/{version.split('.')[0]}/"
        if base != expected:
            violations.append(f"project namespace is <{base}>, expected <{expected}> from docs/_ech.yml")
    if base:
        for prefix, iri in declared_namespaces().items():
            if iri.startswith(base) and iri != base and not SUBNAMESPACE.fullmatch(iri[len(base):]):
                violations.append(f"sub-namespace {prefix}: <{iri}> should be <{base}segment/> with a lowercase segment")
    report("Namespaces not following the convention", violations)


def classify(graph, node, predicates):
    """Returns 'class', 'property', 'shape', 'ontology' or 'individual' for a resource."""
    types = set(graph.objects(node, RDF.type))
    if types & {OWL.Class, RDFS.Class}:
        return "class"
    if node in predicates or types & {RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty}:
        return "property"
    if types & {SH.NodeShape, SH.PropertyShape}:
        return "shape"
    if OWL.Ontology in types:
        return "ontology"
    return "individual"


def test_resource_names_follow_convention(final_graph):
    """
    Local names of resources in the project namespace (CONTRIBUTING.md, "RDF
    resource naming convention"): classes and individuals in PascalCase,
    properties in camelCase without a leading verb, individuals in a
    sub-namespace (identifiers such as person:1 are allowed for individuals).
    """
    base = project_namespace()
    if not base:
        pytest.skip("src/rdf/prefixes.ttl declares no project namespace")

    qname = qname_function()
    predicates = set(final_graph.predicates())
    resources = {node for triple in final_graph for node in triple
                 if isinstance(node, URIRef) and str(node).startswith(base) and str(node) != base}

    violations = {"class": set(), "property": set(), "verb": set(), "individual": set(), "subnamespace": set()}
    for node in sorted(resources):
        local = str(node)[len(base):]
        subnamespace, _, name = local.rpartition("/")
        kind = classify(final_graph, node, predicates)
        if kind == "class":
            if not PASCAL_CASE.fullmatch(name):
                violations["class"].add(f"{qname(node)} (class)")
        elif kind == "property":
            if not CAMEL_CASE.fullmatch(name):
                violations["property"].add(f"{qname(node)} (property)")
            elif VERB_PREFIX.match(name):
                violations["verb"].add(f"{qname(node)} (property)")
        elif kind == "individual":
            kinds = ", ".join(sorted(qname(t) for t in final_graph.objects(node, RDF.type)
                                     if t not in {OWL.NamedIndividual, OWL.Thing})) or "individual"
            if not subnamespace:
                violations["subnamespace"].add(f"{qname(node)} ({kinds})")
            if not (PASCAL_CASE.fullmatch(name) or IDENTIFIER.fullmatch(name)):
                violations["individual"].add(f"{qname(node)} ({kinds})")
        # shapes and the ontology IRI are not covered by the convention

    report("Classes not in PascalCase", violations["class"])
    report("Properties not in camelCase", violations["property"])
    report("Properties starting with a verb (prefer eppoCode over hasEppoCode)", violations["verb"])
    report("Individuals not in PascalCase (or an identifier)", violations["individual"])
    report("Individuals directly in the project namespace instead of a sub-namespace", violations["subnamespace"])
