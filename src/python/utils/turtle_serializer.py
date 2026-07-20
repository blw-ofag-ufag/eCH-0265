import argparse
import glob
import sys
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import NamespaceManager

def main():
    parser = argparse.ArgumentParser(description="Merge and normalize RDF turtle files deterministically.")
    
    parser.add_argument(
        "-i", "--input", 
        nargs="+", 
        required=True,
        help="Path(s) or glob pattern(s) to read (e.g., 'data/*.ttl')."
    )
    
    parser.add_argument(
        "-p", "--prefixes", 
        type=Path,
        default=None,
        help="Path to a .ttl file containing prefix definitions. These strictly override existing prefixes."
    )
    
    parser.add_argument(
        "-o", "--output", 
        type=Path,
        default=None,
        help="Destination path for the serialized graph. Defaults to the input path if only one input is provided."
    )

    args = parser.parse_args()

    # 1. Resolve input paths
    resolved_inputs = []
    for pattern in args.input:
        for file_path in glob.glob(pattern, recursive=True):
            resolved_inputs.append(Path(file_path))
            
    if not resolved_inputs:
        print("Error: No input files found matching the provided pattern(s).", file=sys.stderr)
        sys.exit(1)

    # 2. Output resolution logic
    output_path = args.output
    if not output_path:
        if len(resolved_inputs) == 1:
            output_path = resolved_inputs[0]
        else:
            print("Error: Multiple input files provided but no --output path specified.", file=sys.stderr)
            sys.exit(1)

    # 3. Initialize the main graph WITHOUT default namespaces
    g = Graph(bind_namespaces="none")
    for file_path in resolved_inputs:
        g.parse(file_path, format="turtle")

    # 4. Attach a completely blank namespace manager before binding custom prefixes
    clean_nsm = NamespaceManager(Graph(bind_namespaces="none"))
    g.namespace_manager = clean_nsm

    # 5. Parse custom prefixes
    if args.prefixes:
        if not args.prefixes.exists():
            print(f"Error: Prefix file '{args.prefixes}' does not exist.", file=sys.stderr)
            sys.exit(1)
            
        # Parse the prefix file into a BLANK graph.
        prefix_g = Graph(bind_namespaces="none")
        prefix_g.parse(args.prefixes, format="turtle")
        
        # Apply the exact parsed prefixes to our main graph
        for prefix, uri in prefix_g.namespaces():
            try:
                g.bind(str(prefix), Namespace(str(uri)), override=True, replace=True)
            except TypeError:
                g.bind(str(prefix), Namespace(str(uri)), override=True)

    # 6. Ensure output directory hierarchy exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 7. Serialize output using the standard rdflib turtle serializer
    g.serialize(destination=output_path, format="turtle")

if __name__ == "__main__":
    main()