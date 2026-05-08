#!/bin/bash
set -e # immediately exit on error
source .env


echo "Validate syntax of turtle files"
python src/python/validate.py rdf


echo "Create a dedicated OWL file for subsequent WebVOWL visualization of the crop taxonomy"
python src/python/rdf-processing.py \
  --input rdf/ontology/cultivationtypes.ttl \
  --output rdf/processed/crop-taxonomy.ttl \
  --rules src/sparql/processing-rules/*.sparql


echo "Merge all data into one graph for subsequent LINDAS upload"
python src/python/rdf-processing.py \
  --input rdf/ontology/*.ttl rdf/data/*.ttl rdf/shape/*.ttl \
  --output rdf/processed/graph.ttl \
  --rules src/sparql/inference-rules/*.sparql


echo "Check graph shape using SHACL"
pyshacl rdf/ontology/cultivationtypes.ttl --shapes rdf/shape/metadata-quality.ttl --format human


echo "Delete existing data from LINDAS"
curl \
  --user $USER:$PASSWORD \
  -X DELETE \
  "$ENDPOINT?graph=$GRAPH"


echo "Upload graph.ttl file to LINDAS"
curl \
  --user $USER:$PASSWORD \
  -X POST \
  -H "Content-Type: text/turtle" \
  --data-binary @rdf/processed/graph.ttl \
  "$ENDPOINT?graph=$GRAPH"
