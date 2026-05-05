#!/usr/bin/env python3

"""
AGIS Disjointness Snippet Generator

This script parses an AGIS RDF dataset (in Turtle format) to identify all 
active cultivation types. It defines an "active" crop as a cube:Observation 
where the `schema:validTo` property is explicitly set to `cube:Undefined`.

After querying the dataset via SPARQL, it extracts the integer IDs of these 
active crops, sorts them numerically, and generates an OWL `AllDisjointClasses` 
Turtle snippet. This auto-generated snippet can be appended to your main 
ontology or loaded alongside it in a reasoner to ensure that all active 
cultivation classes are treated as mutually exclusive.

Usage examples:
    python3 script.py -i agis.ttl
    python3 script.py -i agis.ttl -o agis-disjointness.ttl
"""


import argparse
import sys
import rdflib

def generate_disjointness_snippet(agis_ttl_path):
    # 1. Load the AGIS dataset
    g = rdflib.Graph()
    try:
        g.parse(agis_ttl_path, format="turtle")
    except Exception as e:
        print(f"Error parsing {agis_ttl_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. SPARQL query to find all active cultivation types
    query = """
    PREFIX cube: <https://cube.link/>
    PREFIX schema: <http://schema.org/>
    PREFIX crop: <https://agriculture.ld.admin.ch/crops/>

    SELECT ?cultivationType WHERE {
        ?obs a cube:Observation ;
             schema:validTo cube:Undefined ;
             crop:cultivationType ?cultivationType .
    }
    """
    
    results = g.query(query)
    
    # 3. Extract IDs and convert to integers for proper numerical sorting
    active_classes = []
    for row in results:
        class_id = str(row.cultivationType).split('/')[-1]
        try:
            active_classes.append(int(class_id))
        except ValueError:
            print(f"Warning: Could not convert class ID '{class_id}' to integer. Skipping.", file=sys.stderr)
            
    active_classes.sort()

    if not active_classes:
        return "# No active classes found in the provided dataset."

    # 4. Construct the Turtle snippet
    ttl_output = [
        "# ==============================================================================",
        "# ACTIVE AGIS CLASSES DISJOINTNESS (AUTO-GENERATED)",
        "# ==============================================================================",
        "[] a owl:AllDisjointClasses ;",
        "    owl:members ("
    ]
    
    # Batch them into rows of 8 for readability
    for i in range(0, len(active_classes), 8):
        row_items = " ".join([f"cultivationtype:{c}" for c in active_classes[i:i+8]])
        ttl_output.append(f"        {row_items}")
        
    ttl_output.append("    ) .")
    
    return "\n".join(ttl_output)

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description="Generate an OWL disjointness snippet from an AGIS TTL dataset."
    )
    
    parser.add_argument(
        "-i", "--input", 
        type=str, 
        required=True, 
        help="Path to the input AGIS TTL file (e.g., agis.ttl)"
    )
    
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        help="Optional path to output file. If omitted, prints to terminal."
    )

    args = parser.parse_args()

    # Generate the snippet
    snippet = generate_disjointness_snippet(args.input)

    # Handle the output
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(snippet)
                f.write("\n")
            print(f"Success: Snippet written to '{args.output}'")
        except IOError as e:
            print(f"Error writing to {args.output}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(snippet)

if __name__ == "__main__":
    main()