import os
import certifi
import httpx

# Disable SSL verification for HuggingFace Hub
os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '1'
os.environ['CURL_CA_BUNDLE'] = ''

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

class RAGTool:
    def __init__(self, db_path="./chroma_db", collection_name="medical_docs"):
        self.db_path = db_path
        self.collection_name = collection_name
        
        print("Initializing RAGTool with HuggingFaceEmbeddings (Local Model)...")
        try:
            # Use the locally downloaded model path
            model_path = "./local_embeddings_model"
            if os.path.exists(model_path):
                self.embeddings = HuggingFaceEmbeddings(model_name=model_path, model_kwargs={'device': 'cpu'})
            else:
                # Fallback to online if local folder missing (though we just created it)
                self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2", model_kwargs={'device': 'cpu'})
        except Exception as e:
            print(f"Failed to initialize HuggingFaceEmbeddings: {e}")
            # Fallback to OpenAI if HF fails
            # On Windows (Local), we disable SSL verify. On Linux (Cloud), we use default.
            if os.name == 'nt':
                self.http_client = httpx.Client(verify=False)
            else:
                self.http_client = None
            
            self.embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", http_client=self.http_client)

        self.vectorstore = Chroma(persist_directory=self.db_path, embedding_function=self.embeddings, collection_name=self.collection_name)

    def ingest_pdf(self, pdf_path):
        if not os.path.exists(pdf_path):
            print(f"File not found: {pdf_path}")
            return
        
        print(f"Loading PDF: {pdf_path}")
        try:
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            docs = text_splitter.split_documents(documents)
            
            print(f"Split into {len(docs)} chunks. Adding to vectorstore...")
            self.vectorstore.add_documents(docs)
            print(f"Ingested {len(docs)} chunks from {pdf_path}")
        except Exception as e:
            print(f"Error during ingestion: {e}")

    def query(self, query_text, k=3):
        try:
            # Use similarity_search_with_relevance_scores to filter irrelevant results
            # This returns a list of (Document, score) tuples. 
            # Scores are normalized (0 to 1), where 1 is most similar.
            results = self.vectorstore.similarity_search_with_relevance_scores(query_text, k=k)
            
            relevant_content = []
            for doc, score in results:
                # Threshold 0.0: We rely on post-filtering by name in the agent logic
                # to avoid false positives (e.g. "Vimla" matching "Rebeca").
                # This ensures we don't miss "Deepak" (score ~0.13) due to a strict threshold.
                if score > 0.0: 
                    relevant_content.append(doc.page_content)
            
            return relevant_content
        except Exception as e:
            print(f"Error during query with scores: {e}")
            # Fallback to standard search if relevance scoring fails
            try:
                docs = self.vectorstore.similarity_search(query_text, k=k)
                return [doc.page_content for doc in docs]
            except Exception as e2:
                print(f"Error during fallback query: {e2}")
                return []
