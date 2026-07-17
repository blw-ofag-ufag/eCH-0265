# Warning: Please do not adjust this script in any other place than the upstream repo template

import argparse
import re
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import RDFS

SH = Namespace("http://www.w3.org/ns/shacl#")

TRANSLATIONS = {
    "en": {
        "name": "Description",
        "path": "Path",
        "type": "Type",
        "cardinality": "Cardinality",
        "target_class": "Target Class",
        "properties": "properties",
        "or": "or"
    },
    "de": {
        "name": "Beschreibung",
        "path": "Pfad",
        "type": "Typ",
        "cardinality": "Kardinalität",
        "target_class": "Zielklasse",
        "properties": "Eigenschaften",
        "or": "oder"
    },
    "fr": {
        "name": "Description",
        "path": "Chemin",
        "type": "Type",
        "cardinality": "Cardinalité",
        "target_class": "Classe cible",
        "properties": "propriétés",
        "or": "ou"
    },
    "it": {
        "name": "Nome",
        "path": "Percorso",
        "type": "Tipo",
        "cardinality": "Cardinalità",
        "target_class": "Classe di destinazione",
        "properties": "proprietà",
        "or": "o"
    }
}

def format_uri(g, uri):
    if not uri:
        return ""
    try:
        return g.namespace_manager.normalizeUri(uri)
    except Exception:
        return str(uri)

def slugify(text):
    """Creates a URL-friendly slug from a string."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

def sanitize_cell(text):
    """Removes newlines and escapes pipe characters to prevent markdown table breaks."""
    return str(text).replace("\n", " ").replace("\r", "").replace("|", "&#124;").strip()

def get_localized_value(g, subject, predicates, lang):
    """Finds the best matching localized value for a given subject and list of predicates."""
    for predicate in predicates:
        values = {}
        for obj in g.objects(subject, predicate):
            if hasattr(obj, 'language') and obj.language:
                values[obj.language.lower()] = str(obj)
            else:
                values[''] = str(obj)
        if not values:
            continue            
        if lang in values:
            return values[lang]
        if '' in values:
            return values['']
            
    return None

def main():
    parser = argparse.ArgumentParser(description="Generate Markdown documentation from a SHACL model.")
    parser.add_argument("-i", "--input", required=True, help="Input SHACL file (.ttl)")
    parser.add_argument("-d", "--docs_dir", required=True, help="Docs directory containing language subdirectories")
    parser.add_argument("-p", "--prefixes", required=False, help="Prefix file (.ttl) to override QNames")
    args = parser.parse_args()

    g = Graph(bind_namespaces="none")
    g.parse(args.input, format="turtle")

    if args.prefixes:
        prefix_g = Graph(bind_namespaces="none")
        prefix_g.parse(args.prefixes, format="turtle")
        for prefix, uri in prefix_g.namespaces():
            try:
                g.bind(str(prefix), Namespace(str(uri)), override=True, replace=True)
            except TypeError:
                g.bind(str(prefix), Namespace(str(uri)), override=True)

    docs_dir = Path(args.docs_dir)
    languages_to_process = []
    for lang in TRANSLATIONS.keys():
        if (docs_dir / lang).is_dir():
            languages_to_process.append(lang)

    q_classes = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        
        SELECT ?shape ?targetClass
        WHERE {
            ?shape a sh:NodeShape .
            OPTIONAL { ?shape sh:targetClass ?targetClass . }
        }
    """
    
    shapes_list = []
    for row in g.query(q_classes):
        shapes_list.append({
            'uri': row.shape,
            'target_class': row.targetClass
        })

    for lang in languages_to_process:
        md_lines = []
        trans = TRANSLATIONS[lang]
        
        shapes_data = []
        uri_to_slug = {}
        
        for s_info in shapes_list:
            shape_uri = s_info['uri']
            target_class = s_info['target_class']
            
            # Fetch localized label, fall back to QName / technical name
            label = get_localized_value(g, shape_uri, [RDFS.label, SH.name], lang)
            if not label:
                label = format_uri(g, shape_uri)
                
            comment = get_localized_value(g, shape_uri, [RDFS.comment, SH.description], lang) or ""
            
            slug = slugify(label)
            
            uri_to_slug[shape_uri] = slug
            if target_class:
                uri_to_slug[target_class] = slug
                
            shapes_data.append({
                'uri': shape_uri,
                'label': label,
                'comment': comment,
                'target_class': target_class,
                'slug': slug
            })
            
        shapes_data.sort(key=lambda x: x['label'].lower())

        for s_data in shapes_data:
            shape = s_data['uri']
            label = s_data['label']
            comment = s_data['comment']
            target_class = s_data['target_class']
            slug = s_data['slug']

            md_lines.append(f"## {label} {{#sec-{slug}}}")
            md_lines.append("")
            
            if comment:
                md_lines.append(f"{comment}")
                md_lines.append("")
                
            if target_class:
                target_qname = format_uri(g, target_class)
                md_lines.append(f"**{trans['target_class']}:** `{target_qname}`")
                md_lines.append("")

            q_props = """
                PREFIX sh: <http://www.w3.org/ns/shacl#>
                
                SELECT ?prop ?path ?datatype ?class ?minCount ?maxCount ?nodeKind ?order
                WHERE {
                    ?shape sh:property ?prop .
                    OPTIONAL { ?prop sh:path ?path . }
                    OPTIONAL { ?prop sh:datatype ?datatype . }
                    OPTIONAL { ?prop sh:class ?class . }
                    OPTIONAL { ?prop sh:minCount ?minCount . }
                    OPTIONAL { ?prop sh:maxCount ?maxCount . }
                    OPTIONAL { ?prop sh:nodeKind ?nodeKind . }
                    OPTIONAL { ?prop sh:order ?order . }
                } ORDER BY ?order ?path
            """
            
            props = list(g.query(q_props, initBindings={'shape': shape}))
            
            enriched_props = []
            for p in props:
                prop_uri = p["prop"]
                p_name = get_localized_value(g, prop_uri, [SH.name, RDFS.label], lang) or ""
                p_desc = get_localized_value(g, prop_uri, [SH.description, RDFS.comment, SH.message], lang) or ""
                p_path_qname = format_uri(g, p['path']) if p['path'] else ""
                order = p['order'].toPython() if p['order'] else 9999
                
                enriched_props.append({
                    'prop': prop_uri,
                    'name': p_name,
                    'desc': p_desc,
                    'path': p['path'],
                    'path_qname': p_path_qname,
                    'datatype': p['datatype'],
                    'class': p['class'],
                    'minCount': p['minCount'],
                    'maxCount': p['maxCount'],
                    'nodeKind': p['nodeKind'],
                    'order': order
                })
                
            enriched_props.sort(key=lambda x: (x['order'], x['name'].lower(), x['path_qname'].lower()))

            if enriched_props:
                md_lines.append(f"| {trans['name']} | {trans['path']} | {trans['type']} | {trans['cardinality']} |")
                md_lines.append("|:--|:--|:--|--:|")
                
                for p in enriched_props:
                    sh_name = sanitize_cell(p["name"])
                    sh_desc = sanitize_cell(p["desc"])

                    if sh_name and sh_desc:
                        display_name = f"**{sh_name}**: {sh_desc}"
                    elif sh_desc:
                        display_name = sh_desc
                    elif sh_name:
                        display_name = f"**{sh_name}**"
                    else:
                        display_name = ""

                    p_path_str = f"`{p['path_qname']}`" if p["path_qname"] else ""
                    
                    types = []
                    for t_uri in [p["datatype"], p["class"], p["nodeKind"]]:
                        if t_uri:
                            t_qname = format_uri(g, t_uri)
                            if t_uri in uri_to_slug:
                                types.append(f"[{t_qname}](#sec-{uri_to_slug[t_uri]})")
                            else:
                                types.append(f"`{t_qname}`")
                    
                    if not types and p["prop"]:
                        q_or = """
                            PREFIX sh: <http://www.w3.org/ns/shacl#>
                            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                            SELECT ?cls WHERE {
                                ?prop sh:or/rdf:rest*/rdf:first/sh:class ?cls .
                            }
                        """
                        for oc in g.query(q_or, initBindings={'prop': p['prop']}):
                            t_uri = oc.cls
                            t_qname = format_uri(g, t_uri)
                            if t_uri in uri_to_slug:
                                types.append(f"[{t_qname}](#sec-{uri_to_slug[t_uri]})")
                            else:
                                types.append(f"`{t_qname}`")

                    p_type_str = f" {trans['or']} ".join(types)

                    min_c = str(p["minCount"]) if p["minCount"] else "0"
                    max_c = str(p["maxCount"]) if p["maxCount"] else "*"
                    cardinality = f"{min_c}..{max_c}"

                    md_lines.append(f"| {display_name} | {p_path_str} | {p_type_str} | {cardinality} |")
                
                md_lines.append(f": {label} {trans['properties']} {{#tbl-{slug}}}")
                md_lines.append("")

        output_path = docs_dir / lang / "entities.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

if __name__ == "__main__":
    main()