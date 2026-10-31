# Inbox

Drop parsed shard folders here (one folder per match). Do not put raw `.vrf` replays here.

Each shard folder must contain `manifest.json` plus the table files it lists (parquet). See `data/data_pipeline.md` for the format.

To process: open a chat and say "process the inbox". `parser/ingest.py` verifies the schema version, SHA-256 and row counts, rejects bad shards whole, skips matches already in `data/warehouse/catalog.json`, and merges accepted shards into `data/warehouse/` in parts of 8 MB or less.

Keep each commit under about 25 MB if uploading through the GitHub website.
