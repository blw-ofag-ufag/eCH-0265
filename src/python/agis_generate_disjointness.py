#!/usr/bin/env python3

import argparse
import sys
import rdflib
from collections import defaultdict

def generate_hierarchical_disjointness(ontology_path):
    g = rdflib.Graph()
    try:
        g.parse(ontology_path, format="turtle")
    except Exception as e:
        print(f"Error parsing {ontology_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Query all classes and their direct parents
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?subClass ?parentClass WHERE {
        ?subClass a owl:Class .
        ?subClass rdfs:subClassOf ?parentClass .
        FILTER (isIRI(?parentClass))
    }
    """
    
    results = g.query(query)
    
    # Group subclasses by their parent
    parent_to_children = defaultdict(list)
    for row in results:
        sub_class = str(row.subClass)
        parent_class = str(row.parentClass)
        parent_to_children[parent_class].append(sub_class)

    ttl_output = [
        "# ==============================================================================",
        "# SIBLING DISJOINTNESS (AUTO-GENERATED)",
        "# =============================================================================="
    ]

    # Generate disjointness block for parents with >1 child
    for parent, children in parent_to_children.items():
        if len(children) > 1:
            parent_qname = g.qname(parent) if g.qname(parent) else f"<{parent}>"
            
            ttl_output.append(f"\n# Disjoint subclasses of {parent_qname}")
            ttl_output.append("[] a owl:AllDisjointClasses ;")
            ttl_output.append("    owl:members (")
            
            # Format children into the list
            for child in sorted(children):
                child_qname = g.qname(child) if g.qname(child) else f"<{child}>"
                ttl_output.append(f"        {child_qname}")
                
            ttl_output.append("    ) .")

    return "\n".join(ttl_output)

def main():
    parser = argparse.ArgumentParser(description="Generate sibling disjointness from an ontology.")
    parser.add_argument("-i", "--input", type=str, required=True, help="Path to cultivationtypes.ttl")
    parser.add_argument("-o", "--output", type=str, help="Output file. Prints to stdout if omitted.")
    
    args = parser.parse_args()
    snippet = generate_hierarchical_disjointness(args.input)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(snippet)
            f.write("\n")
    else:
        print(snippet)

if __name__ == "__main__":
    main()