import argparse
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import SKOS

SCHEMA = Namespace("http://schema.org/")

TRANSLATIONS = {
    "en": {
        "iri": "IRI", "term": "Term", "desc": "Description", "rels": "Relations",
        "broader": "broader", "narrower": "narrower", "related": "related"
    },
    "de": {
        "iri": "IRI", "term": "Begriff", "desc": "Beschreibung", "rels": "Beziehungen",
        "broader": "Oberbegriff", "narrower": "Unterbegriff", "related": "Verwandt"
    },
    "fr": {
        "iri": "IRI", "term": "Terme", "desc": "Description", "rels": "Relations",
        "broader": "plus générique", "narrower": "plus spécifique", "related": "lié"
    },
    "it": {
        "iri": "IRI", "term": "Termine", "desc": "Descrizione", "rels": "Relazioni",
        "broader": "più generico", "narrower": "più specifico", "related": "correlato"
    }
}

def format_uri(g, uri):
    if not uri:
        return ""
    try:
        return g.namespace_manager.normalizeUri(uri)
    except Exception:
        return str(uri)

def get_localized_value(g, subject, predicates, lang):
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

def sanitize_cell(text):
    return str(text).replace("\n", " ").replace("\r", "").replace("|", "&#124;").strip()

def main():
    parser = argparse.ArgumentParser(description="Generate Markdown documentation from a SKOS glossary.")
    parser.add_argument("-i", "--input", required=True, help="Input SKOS file (.ttl)")
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
    languages_to_process = [lang for lang in TRANSLATIONS.keys() if (docs_dir / lang).is_dir()]

    q_concepts = """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT DISTINCT ?concept WHERE {
            ?concept a skos:Concept .
        }
    """
    concepts = [row.concept for row in g.query(q_concepts)]
    
    q_scheme = """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT DISTINCT ?scheme WHERE {
            ?scheme a skos:ConceptScheme .
        }
    """
    schemes = [row.scheme for row in g.query(q_scheme)]
    scheme = schemes[0] if schemes else None

    for lang in languages_to_process:
        trans = TRANSLATIONS[lang]
        md_lines = []
        
        md_lines.append(f"| {trans['iri']} | {trans['term']} | {trans['desc']} | {trans['rels']} |")
        md_lines.append("|:--|:--|:--|:--|")
        
        # Sort concepts by IRI for stable output
        concepts.sort(key=lambda c: format_uri(g, c).lower())

        for c in concepts:
            iri_qname = format_uri(g, c)
            iri_cell = f"[`{iri_qname}`]({str(c)})"
            
            name = get_localized_value(g, c, [SCHEMA.name, SKOS.prefLabel], lang)
            alt = get_localized_value(g, c, [SCHEMA.alternateName, SKOS.altLabel], lang)
            
            term_str = f"**{name}**" if name else ""
            if alt:
                term_str += f" ({alt})" if term_str else alt
            term_cell = sanitize_cell(term_str)
            
            desc = get_localized_value(g, c, [SCHEMA.description, SKOS.definition], lang) or ""
            desc_cell = sanitize_cell(desc)
            
            rels = []
            for p, label_key in [(SKOS.broader, 'broader'), (SKOS.narrower, 'narrower'), (SKOS.related, 'related')]:
                for o in g.objects(c, p):
                    o_qname = format_uri(g, o)
                    rels.append(f"*{trans[label_key]}*: [`{o_qname}`]({str(o)})")
            rels_cell = sanitize_cell(", ".join(rels))

            md_lines.append(f"| {iri_cell} | {term_cell} | {desc_cell} | {rels_cell} |")
        
        # Build table caption
        caption_text = ""
        if scheme:
            s_name = get_localized_value(g, scheme, [SCHEMA.name, SKOS.prefLabel], lang)
            s_desc = get_localized_value(g, scheme, [SCHEMA.description, SKOS.definition], lang)
            
            s_name_clean = sanitize_cell(s_name) if s_name else ""
            s_desc_clean = sanitize_cell(s_desc) if s_desc else ""
            
            if s_name_clean and s_desc_clean:
                caption_text = f"**{s_name_clean}:** {s_desc_clean}"
            elif s_name_clean:
                caption_text = f"{s_name_clean}"
            elif s_desc_clean:
                caption_text = f"{s_desc_clean}"
        
        if caption_text:
            md_lines.append(f": {caption_text} {{#tbl-glossary tbl-colwidths=\"[15,20,40,25]\" }}")
        else:
            md_lines.append(": {#tbl-glossary tbl-colwidths=\"[15,20,40,25]\"}")
            
        output_path = docs_dir / lang / "glossary.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

if __name__ == "__main__":
    main()