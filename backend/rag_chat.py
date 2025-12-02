from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
# We don't need OpenAI anymore for this test!

class Oracle:
    def __init__(self):
        # 1. Load the Local Embeddings (HuggingFace)
        self.embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # 2. Connect to the Database
        self.db = Chroma(persist_directory="./chroma_db", embedding_function=self.embedding)

    def ask(self, question):
        # --- RAW SEARCH MODE ---
        # Instead of asking GPT to write a sentence, we just grab the top result from the DB.
        
        print(f"Searching DB for: {question}")
        results = self.db.similarity_search(question, k=1)
        
        if not results:
            return "I couldn't find any data on that Pokemon in your database."
            
        # Return the raw text we found
        best_match = results[0]
        return f"**I FOUND THIS DATA:**\n\n{best_match.page_content}"