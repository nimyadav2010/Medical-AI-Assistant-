from tools.rag_tool import RAGTool

def inspect_rag():
    print("Initializing RAG Tool...")
    rag = RAGTool(db_path="./chroma_db")
    
    print("Checking collection count...")
    # Access the underlying collection object from Chroma
    try:
        count = rag.vectorstore._collection.count()
        print(f"Total documents in vectorstore: {count}")
        
        if count > 0:
            print("Peeking at first 3 documents...")
            peek = rag.vectorstore._collection.peek(limit=3)
            print(peek)
            
            print("\nTesting query...")
            results = rag.query("medical history")
            print(f"Query results: {results}")
        else:
            print("Vectorstore is empty.")
            
    except Exception as e:
        print(f"Error inspecting vectorstore: {e}")

if __name__ == "__main__":
    inspect_rag()
