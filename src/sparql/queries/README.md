# SPARQL queries

## Which queries are available?

Ready-to-use SPARQL queries against the published eCH-0265 graph on [LINDAS](https://lindas.admin.ch/). These serve as examples for data consumers and are not part of the build pipeline.

| File | Returns |
|:-----|:--------|
| `all_cultivation_types.rq` | All cultivation types of the reference taxonomy with their German name. |
| `cereal_crops.rq` | The cereal crops of the Suisse-Bilanz crop table with German and French names and identifiers. |
| `mapping_table.rq` | A flat mapping table: every crop with its name, identifier and scheme, together with the crops of the other schemes it maps to (exact, broad or narrow match). |
| `mapping_table_specific_systems.rq` | The mapping table restricted to one pair of systems: currently valid direct payment crops (AGIS) and the plant protection crops (PSM) they map to. |
| `valid_direct_payment_crops.rq` | The direct payment crops (AGIS) valid today with German and French names, identifiers and validity period. |

## How do I run these queries?

Send the query file in the body of an HTTP POST request to the LINDAS endpoint:

``` sh
curl -X POST "https://lindas.admin.ch/query" \
     -H "Content-Type: application/sparql-query" \
     -H "Accept: text/csv" \
     --data-binary @mapping_table.rq -o mapping_table.csv
```

The `Accept` header selects the result format: `text/csv`, `application/sparql-results+json` or `application/sparql-results+xml`. The queries can also be pasted into the [LINDAS SPARQL editor](https://lindas.admin.ch/sparql/).
