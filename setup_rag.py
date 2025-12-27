import os
import sys
print(sys.path)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import glob
from tools.rag_tool import RAGTool

def main():
    # Initialize RAG Tool
    rag = RAGTool(db_path="./chroma_db")
    
    # Find all PDFs in data directory
    pdf_files = glob.glob(os.path.join("data", "*.pdf"))
    
    if not pdf_files:
        print("No PDF files found in data directory.")
        return

    for pdf_path in pdf_files:
        print(f"Ingesting {pdf_path}...")
        rag.ingest_pdf(pdf_path)
    
    print("Ingestion complete.")
    
    # Test query
    print("Testing query...")
    results = rag.query("kidney disease diet")
    for i, res in enumerate(results):
        print(f"Result {i+1}: {res[:200]}...")

if __name__ == "__main__":
    main()
