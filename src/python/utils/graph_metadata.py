# Warning: Please do not adjust this script in any other place than the upstream repo template
"""
Sets the modification date of the dataset that describes the named graph.

Before publishing, the graph to be uploaded is compared with the graph that is
currently on LINDAS. If their content differs, the dataset gets today's date
as schema:dateModified and dcterms:modified; otherwise the date found on
LINDAS is kept. The comparison uses a content fingerprint that ignores blank
node identifiers and the modification date itself.

    python graph_metadata.py --graph build/rdf/03-processed.ttl \\
        --iri https://lindas.admin.ch/foag/ogd \\
        --endpoint https://.../rdf-graphs/service --user ... --password ...

Without --endpoint (or when LINDAS cannot be reached) today's date is set.
"""

import argparse
import base64
import datetime
import hashlib
import re
import sys
import urllib.request
import urllib.error
from rdflib import Graph, Literal, URIRef, BNode
from rdflib.namespace import DCTERMS, XSD

SCHEMA_MODIFIED = URIRef("http://schema.org/dateModified")
DATE_PREDICATES = (SCHEMA_MODIFIED, DCTERMS.modified)


def fingerprint(graph, dataset):
    """SHA-256 over the sorted N-Triples of the graph, with blank node
    identifiers neutralised and the dataset's modification date left out."""
    lines = []
    for s, p, o in graph:
        if s == dataset and p in DATE_PREDICATES:
            continue
        lines.append(" ".join("_:b" if isinstance(t, BNode) else t.n3() for t in (s, p, o)))
    digest = hashlib.sha256()
    for line in sorted(lines):
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def fetch_live_graph(endpoint, iri, user, password):
    """Downloads the named graph from the Graph Store endpoint, or None."""
    request = urllib.request.Request(f"{endpoint}?graph={iri}", headers={"Accept": "text/turtle"})
    if user and password:
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            data = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"Could not fetch the live graph ({e}); treating the graph as changed.")
        return None
    graph = Graph()
    graph.parse(data=data, format="turtle")
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", required=True, help="Turtle file to be published (updated in place)")
    parser.add_argument("--iri", required=True, help="IRI of the named graph (and of the dataset)")
    parser.add_argument("--endpoint", help="Graph Store endpoint (…/rdf-graphs/service)")
    parser.add_argument("--user")
    parser.add_argument("--password")
    args = parser.parse_args()

    dataset = URIRef(args.iri)
    local = Graph()
    local.parse(args.graph, format="turtle")
    if (dataset, None, None) not in local:
        sys.exit(f"The graph contains no triples about the dataset <{args.iri}>; see src/rdf/metadata.ttl.")

    live = fetch_live_graph(args.endpoint, args.iri, args.user, args.password) if args.endpoint else None
    live_date = next((o for o in live.objects(dataset, SCHEMA_MODIFIED)), None) if live is not None else None

    if live is not None and live_date is not None and fingerprint(live, dataset) == fingerprint(local, dataset):
        date = Literal(str(live_date), datatype=XSD.date)
        print(f"Graph unchanged; keeping modification date {date}.")
    else:
        date = Literal(datetime.date.today().isoformat(), datatype=XSD.date)
        print(f"Graph changed; setting modification date {date}.")

    for predicate in DATE_PREDICATES:
        local.remove((dataset, predicate, None))
        local.add((dataset, predicate, date))

    with open(args.graph, "a", encoding="utf-8") as f:
        f.write("\n")
        for predicate in DATE_PREDICATES:
            f.write(f"<{dataset}> <{predicate}> {date.n3()} .\n")


if __name__ == "__main__":
    main()
