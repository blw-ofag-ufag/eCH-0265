import warnings
import pytest

def test_no_duplicate_names(cultivation_graph):
    """
    Ensures that no two distinct cultivation types share the exact same schema:name
    in the same language. Issues a warning if duplicates are found.
    """
    query = """
    PREFIX schema: <http://schema.org/>
    
    SELECT ?name ?lang (GROUP_CONCAT(DISTINCT STR(?subject); separator=", ") AS ?subjects)
    WHERE {
        ?subject schema:name ?name .
        BIND(LANG(?name) AS ?lang)
        
        # Restrict to the cultivationtype namespace
        FILTER(STRSTARTS(STR(?subject), "https://agriculture.ld.admin.ch/crops/cultivationtype/"))
    }
    GROUP BY ?name ?lang
    HAVING (COUNT(DISTINCT ?subject) > 1)
    """
    
    results = list(cultivation_graph.query(query))
    
    if results:
        error_details = []
        for row in results:
            subjects = [s.split('/')[-1] for s in str(row.subjects).split(', ')]
            error_details.append(f"  → Name: '{row.name}'@{row.lang} | Used in IDs: {subjects}")
            
        warning_msg = f"Duplicate schema:name warning: Found {len(results)} duplicate entries across different cultivation types:\n" 
        
        # Limit output length to match the completeness warning style
        warning_msg += "\n".join(error_details[:50])
        if len(error_details) > 50:
            warning_msg += f"\n  ... and {len(error_details) - 50} more."
            
        warnings.warn(warning_msg, UserWarning)


def test_language_completeness_warning(cultivation_graph):
    """
    Checks that every cultivation type has a schema:name in 'de', 'fr', 'it', and 'en'.
    Issues a warning detailing the missing translations instead of failing the test.
    """
    required_langs = {"de", "fr", "it", "en"}
    
    query = """
    PREFIX schema: <http://schema.org/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT ?subject (GROUP_CONCAT(DISTINCT LANG(?name); separator=",") AS ?langs)
    WHERE {
        ?subject a ?type .
        FILTER (?type IN (owl:Class, owl:DeprecatedClass))
        FILTER(STRSTARTS(STR(?subject), "https://agriculture.ld.admin.ch/crops/cultivationtype/"))
        
        OPTIONAL { ?subject schema:name ?name }
    }
    GROUP BY ?subject
    """
    
    results = list(cultivation_graph.query(query))
    missing_details = []
    
    for row in results:
        subject_id = str(row.subject).split('/')[-1]
        
        # Handle cases where no schema:name exists at all
        if not row.langs:
            present_langs = set()
        else:
            present_langs = set(str(row.langs).split(','))
            
        missing_langs = required_langs - present_langs
        
        if missing_langs:
            missing_details.append(f"  → ID: {subject_id} | Missing: {', '.join(sorted(missing_langs))}")
            
    if missing_details:
        warning_msg = (
            f"Language completeness warning: Found {len(missing_details)} cultivation types "
            f"missing one or more required schema:name translations (de, fr, it, en):\n"
        )
        # Limit output length to prevent console flooding if the list is massive
        warning_msg += "\n".join(missing_details[:50])
        if len(missing_details) > 50:
            warning_msg += f"\n  ... and {len(missing_details) - 50} more."
            
        warnings.warn(warning_msg, UserWarning)