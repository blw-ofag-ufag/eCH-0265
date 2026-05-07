#!/usr/bin/env python3

import argparse
import sys
import rdflib
from collections import defaultdict

def generate_agis_disjointness(agis_path, ontology_path):
    # 1. Parse AGIS data to build a whitelist of active groups and types
    g_agis = rdflib.Graph()
    try:
        g_agis.parse(agis_path, format="turtle")
    except Exception as e:
        print(f"Error parsing {agis_path}: {e}", file=sys.stderr)
        sys.exit(1)

    query_agis = """
    PREFIX crop: <https://agriculture.ld.admin.ch/crops/>
    SELECT DISTINCT ?group ?type WHERE {
        ?obs crop:cultivationGroup ?group ;
             crop:cultivationType ?type .
    }
    """
    
    valid_agis_types = set()
    valid_agis_groups = set()
    
    for row in g_agis.query(query_agis):
        if row.type:
            valid_agis_types.add(str(row.type))
        if row.group:
            valid_agis_groups.add(str(row.group))

    # 2. Parse Ontology to get the hierarchy
    g_onto = rdflib.Graph()
    try:
        g_onto.parse(ontology_path, format="turtle")
    except Exception as e:
        print(f"Error parsing {ontology_path}: {e}", file=sys.stderr)
        sys.exit(1)

    query_onto = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?subClass ?parentClass WHERE {
        ?subClass a owl:Class .
        ?subClass rdfs:subClassOf ?parentClass .
        FILTER (isIRI(?parentClass))
    }
    """
    
    parent_to_children = defaultdict(list)
    for row in g_onto.query(query_onto):
        sub_class = str(row.subClass)
        parent_class = str(row.parentClass)
        
        # FILTER: Only include the subclass if it is an official AGIS type
        if sub_class in valid_agis_types:
            parent_to_children[parent_class].append(sub_class)

    ttl_output = [
        "# ==============================================================================",
        "# AGIS-SPECIFIC DISJOINTNESS (AUTO-GENERATED)",
        "# =============================================================================="
    ]
    
    # 3. Generate disjointness for the Cultivation Groups found in AGIS
    if len(valid_agis_groups) > 1:
        ttl_output.append("\n# Disjoint AGIS Cultivation Groups")
        ttl_output.append("[] a owl:AllDisjointClasses ;")
        ttl_output.append("    owl:members (")
        for grp in sorted(valid_agis_groups):
            grp_qname = g_onto.qname(grp) if g_onto.qname(grp) else f"<{grp}>"
            ttl_output.append(f"        {grp_qname}")
        ttl_output.append("    ) .")

    # 4. Generate disjointness for the Cultivation Types (Siblings)
    for parent, children in parent_to_children.items():
        if len(children) > 1:
            parent_qname = g_onto.qname(parent) if g_onto.qname(parent) else f"<{parent}>"
            
            ttl_output.append(f"\n# Disjoint AGIS subclasses of {parent_qname}")
            ttl_output.append("[] a owl:AllDisjointClasses ;")
            ttl_output.append("    owl:members (")
            
            for child in sorted(children):
                child_qname = g_onto.qname(child) if g_onto.qname(child) else f"<{child}>"
                ttl_output.append(f"        {child_qname}")
                
            ttl_output.append("    ) .")

    return "\n".join(ttl_output)

def main():
    parser = argparse.ArgumentParser(description="Generate AGIS-specific disjointness from an ontology.")
    parser.add_argument("-a", "--agis", type=str, required=True, help="Path to agis.ttl")
    parser.add_argument("-o", "--ontology", type=str, required=True, help="Path to cultivationtypes.ttl")
    parser.add_argument("-out", "--output", type=str, help="Output file. Prints to stdout if omitted.")
    
    args = parser.parse_args()
    snippet = generate_agis_disjointness(args.agis, args.ontology)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(snippet)
            f.write("\n")
    else:
        print(snippet)

if __name__ == "__main__":
    main()