
import os
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import create_engine, text, MetaData, Table, select
from dotenv import load_dotenv
from pgvector.sqlalchemy import Vector

from backend.app.services.embedding_service import embedding_service

# --- Database Setup ---
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Reflect existing tables
document_chunks = Table('document_chunks', metadata, autoload_with=engine)
document_content = Table('document_content', metadata, autoload_with=engine)


class RAGAgent:
    """
    Agent for performing Retrieval-Augmented Generation tasks.
    # This class handles all RAG-related logic.
    """
    def search(self, user_prompt: str, unique_content_id: int, top_k: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Performs a multi-modal RAG search and returns a dictionary separating
        text chunks from full page content.

        Args:
            user_prompt: The user's query.
            unique_content_id: The ID of the specific document to search within.
            top_k: The number of top similar chunks to retrieve. If None, it will be read from RAG_TOP_K environment variable, defaulting to 3.

        Returns:
            A dictionary with two keys:
            - "text_chunks": A list of lightweight text chunks for debugging/planning.
            - "page_content": A list of heavyweight structured page content for generation.
        """
        if top_k is None:
            top_k = int(os.getenv("RAG_TOP_K", "3"))
        
        print(f"--- RAGAgent: Starting Search for prompt: '{user_prompt}' within document ID: {unique_content_id} ---")

        # Step 1: Vector Search (Text RAG)
        print(f"RAGAgent: Step 1 - Performing vector search for top {top_k} chunks...")
        query_embedding = embedding_service.create_embeddings([user_prompt])[0][0]

        stmt = text(f"""
            SELECT id, chunk_text, metadata, multimodal_metadata,
                   1 - (embedding <=> :query_embedding) AS similarity_score
            FROM {document_chunks.name}
            WHERE unique_content_id = :unique_content_id
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k
        """)

        with engine.connect() as conn:
            similar_chunks_results = conn.execute(
                stmt,
                {"query_embedding": str(query_embedding), "unique_content_id": unique_content_id, "top_k": top_k}
            ).fetchall()

        if not similar_chunks_results:
            print("RAGAgent: No similar chunks found for the given document ID.")
            return {"text_chunks": [], "page_content": []}
        
        print(f"RAGAgent: Found {len(similar_chunks_results)} similar chunks.")

        # Process found text chunks for debugging and to find page numbers
        found_text_chunks = []
        page_numbers_to_retrieve = set()
        for chunk in similar_chunks_results:
            chunk_id, chunk_text, meta, mm_meta, sim_score = chunk
            page_numbers = meta.get("page_numbers", [])
            page_numbers_to_retrieve.update(page_numbers)
            found_text_chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "source_pages": page_numbers,
                "similarity_score": round(float(sim_score), 4),  # Cosine similarity (0-1)
                "multimodal_metadata": mm_meta
            })

        # Step 2 & 3: Retrieve Full Multimodal Content
        print("RAGAgent: Step 2 & 3 - Retrieving full multimodal content for relevant pages...")
        found_page_content = []
        if page_numbers_to_retrieve:
            print(f"RAGAgent: Querying structured content for document ID {unique_content_id}, pages: {list(page_numbers_to_retrieve)}")
            
            page_numbers_str = ", ".join(map(str, page_numbers_to_retrieve))
            content_stmt = text(f"""
                SELECT page_number, structured_content, combined_human_text
                FROM {document_content.name}
                WHERE unique_content_id = :unique_content_id AND page_number IN ({page_numbers_str})
                ORDER BY page_number
            """)
            
            with engine.connect() as conn:
                retrieved_pages = conn.execute(content_stmt, {"unique_content_id": unique_content_id}).fetchall()

            for page in retrieved_pages:
                page_num, structured_data, human_text = page
                found_page_content.append({
                    "type": "structured_page_content",
                    "source_document_id": unique_content_id,
                    "page_number": page_num,
                    "content": structured_data,
                    "combined_human_text": human_text  # Full human-readable text for this page
                })
        
        print("RAGAgent: --- Search Finished ---")
        return {
            "text_chunks": found_text_chunks,
            "page_content": found_page_content
        }

# Singleton instance for easy access
rag_agent = RAGAgent()

if __name__ == '__main__':
    # Example usage:
    # Ensure you have run the ingestion_orchestrator first to populate data
    # from app.agents.ingestion_orchestrator import process_file
    # process_file(file_path="test_files/sample2.pdf", uploader_id=1, course_id=1, force_reprocess=True)
    
    # Mock a unique_content_id that exists in your DB after ingestion
    # You might need to manually find an ID from your 'unique_contents' table
    MOCK_UNIQUE_CONTENT_ID = 1 # Replace with an actual ID from your DB
    
    if MOCK_UNIQUE_CONTENT_ID == 1:
        print("WARNING: MOCK_UNIQUE_CONTENT_ID is still 1. Please replace with an actual ID from your 'unique_contents' table for a real test.")

    test_prompt = "What is the role of a Principal Investigator in clinical trials?"
    
    if MOCK_UNIQUE_CONTENT_ID:
        search_result = rag_agent.search(test_prompt, MOCK_UNIQUE_CONTENT_ID)
        
        import json
        print("\n--- RAGAgent Search Result ---")
        print(json.dumps(search_result, indent=2, ensure_ascii=False))
        print("-----------------------------\n")
    else:
        print("Skipping RAGAgent test as MOCK_UNIQUE_CONTENT_ID is not set.")
