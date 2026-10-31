# Warehouse

Merged output of `parser/ingest.py`. Written by the ingest step, not by hand.

- `catalog.json`: matches already ingested (used to skip duplicates)
- `<table>/part-NNNN.parquet`: merged tables, each part 8 MB or less
