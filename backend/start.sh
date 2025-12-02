#!/bin/bash

# 1. Data Check
if [ ! -s "pokemon_db.json" ]; then
    echo "--- Scraping PokeAPI... ---"
    python ingest_data.py
fi

# 2. FORCE REBUILD (Modified)
# We removed the 'rm' command. We will let rag_builder write into the folder.
echo "--- FORCE REBUILDING VECTOR DB ---"
python rag_builder.py

# 3. Start Server
echo "--- Starting Server ---"
uvicorn main:app --host 0.0.0.0 --port 8000