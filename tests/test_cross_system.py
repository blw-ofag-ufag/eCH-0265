import pytest
import requests
import csv
import io
from rdflib import Graph
from rdflib.namespace import RDFS, OWL

CSV_URL = "https://raw.githubusercontent.com/BLV-OSAV-USAV/PSMV-RDF/refs/heads/main/data/raw/Code.csv"

def is_owl_subclass(g, child, parent, visited=None):
    """
    Recursively checks if 'child' is a subclass of 'parent' in the graph 'g'.
    Accounts for rdfs:subClassOf, owl:intersectionOf, and owl:unionOf.
    This resolves the issue of different hierarchical levels (level-skipping).
    """
    if visited is None:
        visited = set()
    
    if child == parent:
        return True
    if child in visited:
        return False
    
    visited.add(child)

    # 1. Direct subClassOf
    for supercls in g.objects(child, RDFS.subClassOf):
        if is_owl_subclass(g, supercls, parent, visited):
            return True

    # 2. Child is an intersection: child ⊑ parent if any intersection member ⊑ parent
    for intersect_list in g.objects(child, OWL.intersectionOf):
        for member in g.items(intersect_list):
            if is_owl_subclass(g, member, parent, set(visited)):
                return True

    # 3. Parent is a union: child ⊑ parent if child ⊑ any union member
    for union_list in g.objects(parent, OWL.unionOf):
        for member in g.items(union_list):
            if is_owl_subclass(g, child, member, set(visited)):
                return True
                
    # 4. Child is a union: child ⊑ parent ONLY if ALL union members ⊑ parent
    for union_list in g.objects(child, OWL.unionOf):
        members = list(g.items(union_list))
        if members and all(is_owl_subclass(g, m, parent, set(visited)) for m in members):
            return True

    return False


def test_culture_consistency_in_rdf(srppp_graph, core_graph):
    """
    Tests that the hierarchy and localized names in the remote CSV 
    EXACTLY MATCH the local RDF graphs.
    """
    try:
        response = requests.get(CSV_URL, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Failed to download CSV from {CSV_URL}\nError: {e}")

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

    combined_graph = Graph()
    combined_graph += srppp_graph
    combined_graph += core_graph

    rdf_hierarchy = set()
    rdf_names = set()

    sparql_hierarchy = """
    PREFIX cube: <https://cube.link/>
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?id ?parent_id
    WHERE {
      [
        a/rdfs:subClassOf* cube:Observation ;
        schema:identifier ?id ;
        schema:isPartOf / schema:identifier ?parent_id
      ]
    }
    """
    for row in combined_graph.query(sparql_hierarchy):
        rdf_hierarchy.add((str(row.id).strip(), str(row.parent_id).strip()))

    sparql_names = """
    PREFIX cube: <https://cube.link/>
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?id ?name
    WHERE {
      ?obs a/rdfs:subClassOf* cube:Observation ;
           schema:identifier ?id ;
           schema:name ?name .
    }
    """
    for row in combined_graph.query(sparql_names):
        r_id = str(row.id).strip()
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
        if not is_owl_subclass(combined_graph, crop_type, group_type):
            c_id = crop.split('/')[-1]
            ct_id = crop_type.split('/')[-1]
            gt_id = group_type.split('/')[-1]
            errors.append(f"[AGIS] Crop {c_id}: Type <{ct_id}> is NOT a subclass of Group <{gt_id}>.")

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
        if not is_owl_subclass(combined_graph, child_type, parent_type):
            cc_id = child.split('/')[-1]
            pc_id = parent.split('/')[-1]
            ct_id = child_type.split('/')[-1]
            pt_id = parent_type.split('/')[-1]
            errors.append(f"[SRPPP] Child {cc_id} <{ct_id}> is NOT a subclass of Parent {pc_id} <{pt_id}>.")

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
        
        # SubCategory -> Category
        if not is_owl_subclass(combined_graph, subcat, cat):
            errors.append(f"[NAEBI] Crop {c_id}: SubCat <{subcat.split('/')[-1]}> NOT a subclass of Cat <{cat.split('/')[-1]}>.")
        
        # Type -> SubCategory (Skip if cultivationType is explicitly mapped to cube:Undefined)
        if ctype and str(ctype) != "https://cube.link/Undefined":
            if not is_owl_subclass(combined_graph, ctype, subcat):
                errors.append(f"[NAEBI] Crop {c_id}: Type <{ctype.split('/')[-1]}> NOT a subclass of SubCat <{subcat.split('/')[-1]}>.")

    if errors:
        error_msg = f"Found {len(errors)} hierarchy inconsistencies across systems:\n"
        for e in errors[:20]:
            error_msg += f"  - {e}\n"
        if len(errors) > 20:
            error_msg += f"  ... and {len(errors) - 20} more."
        pytest.fail(error_msg.strip())