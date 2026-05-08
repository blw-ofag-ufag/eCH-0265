import os
import pandas as pd
from rdflib import Graph, URIRef
from openpyxl.utils import get_column_letter

def extract_dataset_name(g: Graph) -> str:
    """Extracts the dataset schema:name in German to use as the sheet name."""
    query = """
    PREFIX schema: <http://schema.org/>
    PREFIX void: <http://rdfs.org/ns/void

    SELECT ?name WHERE {
        ?s a void:Dataset .
        ?s schema:name ?name .
        FILTER(lang(?name) = 'de')
    } LIMIT 1
    """
    for row in g.query(query):

        return str(row.name)[:31]
    return "Unbekannter_Datensatz"

def extract_crops(g: Graph) -> pd.DataFrame:
    """Extracts crop observations and their attributes."""
    query = """
    PREFIX schema: <http://schema.org/>
    PREFIX cube: <https://cube.link/>

    SELECT ?crop ?id ?name ?validFrom ?validTo WHERE {
        ?crop a ?class .
        VALUES ?class { :DirectPaymentCrop :NutrientBalanceCrop :PlantProtectionCrop }
        ?crop schema:name ?name .
        FILTER(lang(?name) = 'de')

        OPTIONAL { ?crop schema:identifier ?id . }
        OPTIONAL { ?crop schema:validFrom ?validFrom . }
        OPTIONAL { ?crop schema:validTo ?validTo . }
    }
    """

    rows = []
    cube_undefined = URIRef("https://cube.link/Undefined")

    for row in g.query(query):
        valid_to = None
        if row.validTo and row.validTo != cube_undefined:
            valid_to = str(row.validTo)

        rows.append({
            "Kultur-URI": str(row.crop),
            "Identifikator": str(row.id) if row.id else None,
            "Name (de)": str(row.name),
            "Gültig von": str(row.validFrom) if row.validFrom else None,
            "Gültig bis": valid_to
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.dropna(axis=1, how='all')

    return df

def autofit_columns(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame):
    """Auto-adjusts column widths based on content length."""
    worksheet = writer.sheets[sheet_name]

    for idx, col in enumerate(df.columns):

        max_len = max(
            df[col].astype(str).map(len).max() if not df[col].empty else 0,
            len(str(col))
        )

        adjusted_width = max_len + 2

        col_letter = get_column_letter(idx + 1)
        worksheet.column_dimensions[col_letter].width = adjusted_width

def main():
    input_files = [
        'rdf/data/agis.ttl', 
        'rdf/data/naebi.ttl', 
        'rdf/data/srppp.ttl'
    ]
    output_file = 'data/crops.xlsx'

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for file_path in input_files:
            if not os.path.exists(file_path):
                print(f"Warning: File not found: {file_path}")
                continue

            print(f"Processing {file_path}...")
            g = Graph()
            g.parse(file_path, format="turtle")

            sheet_name = extract_dataset_name(g)

            safe_sheet_name = sheet_name.replace(':', '-').replace('/', '-')

            df = extract_crops(g)

            if df.empty:
                print(f"No data found for {safe_sheet_name}, skipping sheet.")
                continue

            df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

            autofit_columns(writer, safe_sheet_name, df)

    print(f"\nExcel file successfully created at: {output_file}")

if __name__ == "__main__":
    main()