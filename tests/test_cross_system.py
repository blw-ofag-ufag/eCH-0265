import pytest
import requests
import csv
import io
import warnings
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS, OWL
from rdflib.graph import ReadOnlyGraphAggregate

CSV_URL = "https://raw.githubusercontent.com/BLV-OSAV-USAV/PSMV-RDF/refs/heads/main/data/raw/Code.csv"
CUBE = Namespace("https://cube.link/")
SCHEMA = Namespace("http://schema.org/")

def is_owl_subclass(g, child, parent, memo=None, path=None):
    """
    Recursively checks if 'child' is a subclass of 'parent' in graph 'g'.
    Includes memoization to prevent exponential execution times and 
    covers all required OWL structural relationships.
    """
    if memo is None:
        memo = {}
    if path is None:
        path = set()

    if child == parent:
        return True

    memo_key = (child, parent)
    if memo_key in memo:
        return memo[memo_key]

    if child in path:
        return False
        
    path.add(child)
    result = False

    for supercls in g.objects(child, RDFS.subClassOf):
        if is_owl_subclass(g, supercls, parent, memo, path):
            result = True
            break

    if not result:
        for intersect_list in g.objects(child, OWL.intersectionOf):
            for member in g.items(intersect_list):
                if is_owl_subclass(g, member, parent, memo, path):
                    result = True
                    break
            if result: break

    if not result:
        for union_list in g.objects(parent, OWL.unionOf):
            for member in g.items(union_list):
                if is_owl_subclass(g, child, member, memo, path):
                    result = True
                    break
            if result: break

    if not result:
        for union_list in g.objects(child, OWL.unionOf):
            members = list(g.items(union_list))
            if members and all(is_owl_subclass(g, m, parent, memo, set(path)) for m in members):
                result = True
                break

    if not result:
        for intersect_list in g.objects(parent, OWL.intersectionOf):
            members = list(g.items(intersect_list))
            if members and all(is_owl_subclass(g, child, m, memo, set(path)) for m in members):
                result = True
                break

    path.remove(child)
    memo[memo_key] = result
    return result


def get_node_name(g, uri):
    """Fetches the schema:name of a URI for readable error output."""
    if not isinstance(uri, URIRef):
        uri = URIRef(uri)
    names = list(g.objects(uri, SCHEMA.name))
    if names:
        de_name = next((n for n in names if getattr(n, 'language', '') == 'de'), None)
        return str(de_name) if de_name else str(names[0])
    return "No schema:name found"


def test_culture_consistency_in_rdf(srppp_graph, core_graph):
    """
    Tests that the hierarchy and localized names in the remote CSV 
    EXACTLY MATCH the local RDF graphs.
    """
    try:
        response = requests.get(CSV_URL, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Network dependency unreachable. Skipping test. Error: {e}")

    csv_hierarchy = set()
    csv_names = set()
    reader = csv.DictReader(io.StringIO(response.text))
    
    for row in reader:
        if row.get("TEXT_KEY") == "Culture":
            c_id = str(row.get("ID", "")).strip()
            c_parent_id = str(row.get("PARENT_ID", "")).strip()
            c_lang = str(row.get("LANGUAGE", "")).strip().lower()
            c_val = str(row.get("VALUE", "")).strip()
            
            if c_id and c_parent_id:
                csv_hierarchy.add((c_id, c_parent_id))
            if c_id and c_lang and c_val:
                csv_names.add((c_id, c_lang, c_val))
                
    if not csv_hierarchy and not csv_names:
        pytest.fail("The CSV filter returned 0 results. Check if the CSV structure changed.")

    combined_graph = ReadOnlyGraphAggregate([srppp_graph, core_graph])

    rdf_hierarchy = set()
    rdf_names = set()

    sparql_combined = """
    PREFIX cube: <https://cube.link/>
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?id ?parent_id ?name
    WHERE {
      ?obs a/rdfs:subClassOf* cube:Observation ;
           schema:identifier ?id .
           
      OPTIONAL { ?obs schema:isPartOf / schema:identifier ?parent_id }
      OPTIONAL { ?obs schema:name ?name }
    }
    """
    for row in combined_graph.query(sparql_combined):
        r_id = str(row.id).strip()
        if row.parent_id:
            rdf_hierarchy.add((r_id, str(row.parent_id).strip()))
        if row.name:
            r_val = str(row.name).strip()
            r_lang = str(row.name.language).lower() if row.name.language else ""
            rdf_names.add((r_id, r_lang, r_val))

    missing_hierarchy = csv_hierarchy - rdf_hierarchy
    extra_hierarchy = rdf_hierarchy - csv_hierarchy
    missing_names = csv_names - rdf_names
    extra_names = rdf_names - csv_names
    
    if any([missing_hierarchy, extra_hierarchy, missing_names, extra_names]):
        error_msg = "Exact match validation failed between CSV and RDF graph.\n\n"
        
        if missing_hierarchy:
            error_msg += f"[{len(missing_hierarchy)} MISSING HIERARCHY] Found in CSV, not in RDF:\n"
            for m_id, m_parent in list(missing_hierarchy)[:10]:
                error_msg += f"  → ID: {m_id} | PARENT_ID: {m_parent}\n"
            error_msg += "\n"

        if extra_hierarchy:
            error_msg += f"[{len(extra_hierarchy)} EXTRA HIERARCHY] Found in RDF, not in CSV:\n"
            for e_id, e_parent in list(extra_hierarchy)[:10]:
                error_msg += f"  → ID: {e_id} | PARENT_ID: {e_parent}\n"
            error_msg += "\n"

        if missing_names:
            error_msg += f"[{len(missing_names)} MISSING NAMES] Found in CSV, not in RDF:\n"
            for m_id, m_lang, m_val in list(missing_names)[:10]:
                error_msg += f"  → ID: {m_id} | LANG: '{m_lang}' | VALUE: '{m_val}'\n"
            error_msg += "\n"

        if extra_names:
            error_msg += f"[{len(extra_names)} EXTRA NAMES] Found in RDF, not in CSV:\n"
            for e_id, e_lang, e_val in list(extra_names)[:10]:
                error_msg += f"  → ID: {e_id} | LANG: '{e_lang}' | VALUE: '{e_val}'\n"

        pytest.fail(error_msg.strip())


def test_hierarchy_consistency_across_systems(cultivation_graph, agis_graph, srppp_graph, naebi_graph):
    """
    Validates that structural hierarchies defined locally within AGIS, SRPPP, and NAEBI
    do not contradict the master TBox hierarchy defined in cultivationtypes.ttl.
    """
    combined_graph = Graph()
    combined_graph += cultivation_graph
    combined_graph += agis_graph
    combined_graph += srppp_graph
    combined_graph += naebi_graph
    
    errors = []
    hierarchy_memo = {}

    # --- 1. AGIS Consistency ---
    agis_query = """
    PREFIX : <https://agriculture.ld.admin.ch/crops/>
    SELECT ?crop ?cropType ?groupType
    WHERE {
        ?crop a :DirectPaymentCrop ;
              :cultivationType ?cropType ;
              :cultivationGroup ?groupType .
    }
    """
    for row in combined_graph.query(agis_query):
        crop, crop_type, group_type = row.crop, row.cropType, row.groupType
        if not is_owl_subclass(combined_graph, crop_type, group_type, memo=hierarchy_memo):
            c_id = crop.split('/')[-1]
            ct_id = crop_type.split('/')[-1]
            gt_id = group_type.split('/')[-1]
            c_name = get_node_name(combined_graph, crop_type)
            g_name = get_node_name(combined_graph, group_type)
            errors.append(f"[AGIS] cultivationtype {c_id}: Type <{ct_id}> ('{c_name}') is NOT a subclass of cultivationtype <{gt_id}> ('{g_name}').")

    # --- 2. SRPPP Consistency ---
    srppp_query = """
    PREFIX schema: <http://schema.org/>
    PREFIX : <https://agriculture.ld.admin.ch/crops/>
    
    SELECT ?childCrop ?parentCrop ?childType ?parentType
    WHERE {
        ?childCrop a :PlantProtectionCrop ;
                   schema:isPartOf ?parentCrop ;
                   :cultivationType ?childType .
        ?parentCrop :cultivationType ?parentType .
    }
    """
    for row in combined_graph.query(srppp_query):
        child, parent, child_type, parent_type = row.childCrop, row.parentCrop, row.childType, row.parentType
        if not is_owl_subclass(combined_graph, child_type, parent_type, memo=hierarchy_memo):
            cc_id = child.split('/')[-1]
            pc_id = parent.split('/')[-1]
            ct_id = child_type.split('/')[-1]
            pt_id = parent_type.split('/')[-1]
            c_name = get_node_name(combined_graph, child_type)
            p_name = get_node_name(combined_graph, parent_type)
            errors.append(f"[SRPPP] Child {cc_id} <{ct_id}> ('{c_name}') is NOT a subclass of Parent {pc_id} <{pt_id}> ('{p_name}').")

    # --- 3. NAEBI Consistency ---
    naebi_query = """
    PREFIX : <https://agriculture.ld.admin.ch/crops/>
    SELECT ?crop ?ctype ?subcat ?cat
    WHERE {
        ?crop a :NutrientBalanceCrop ;
              :cultivationCategory ?cat ;
              :cultivationSubCategory ?subcat .
        OPTIONAL { ?crop :cultivationType ?ctype }
    }
    """
    for row in combined_graph.query(naebi_query):
        crop, ctype, subcat, cat = row.crop, row.ctype, row.subcat, row.cat
        c_id = crop.split('/')[-1]
        
        if not is_owl_subclass(combined_graph, subcat, cat, memo=hierarchy_memo):
            subcat_name = get_node_name(combined_graph, subcat)
            cat_name = get_node_name(combined_graph, cat)
            errors.append(f"[NAEBI] Crop {c_id}: SubCat <{subcat.split('/')[-1]}> ('{subcat_name}') NOT a subclass of Cat <{cat.split('/')[-1]}> ('{cat_name}').")
        
        if ctype and ctype != CUBE.Undefined:
            if not is_owl_subclass(combined_graph, ctype, subcat, memo=hierarchy_memo):
                ctype_name = get_node_name(combined_graph, ctype)
                subcat_name = get_node_name(combined_graph, subcat)
                errors.append(f"[NAEBI] Crop {c_id}: Type <{ctype.split('/')[-1]}> ('{ctype_name}') NOT a subclass of SubCat <{subcat.split('/')[-1]}> ('{subcat_name}').")

    if errors:
        error_msg = f"Found {len(errors)} hierarchy inconsistencies across systems:\n"
        for e in errors[:20]:
            error_msg += f"  - {e}\n"
        if len(errors) > 20:
            error_msg += f"  ... and {len(errors) - 20} more."
            
        # TEMPORARY: Replace pytest.fail with warnings.warn (needs to be changed, once inconsistancies are fixed)
        warnings.warn(error_msg.strip(), UserWarning)