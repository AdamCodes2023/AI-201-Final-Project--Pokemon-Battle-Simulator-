import json, os
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings  # <--- MUST BE THIS
from langchain.schema import Document

def build():
    with open("pokemon_db.json") as f: data = json.load(f)
    docs = []
    for p in data:
        content = f"Name: {p['name']}. Type: {p['types']}. Stats: {p['stats']}."
        docs.append(Document(page_content=content, metadata={"name": p['name']}))
    
    print("Loading Local Embedding Model (Runs on CPU)...")
    # This downloads a free model. It does NOT use an API Key.
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print(f"Embedding {len(docs)} Pokemon...")
    # Persist to disk
    Chroma.from_documents(docs, embeddings, persist_directory="./chroma_db")
    print("DB Built Successfully")

if __name__ == "__main__": build()