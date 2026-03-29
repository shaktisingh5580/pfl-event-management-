"""
tools/pdf_ingestion_tool.py
Handles parsing organizer PDFs, chunking the text, generating embeddings,
and storing them in Supabase for the AI Architect to use.
"""
import io
import json
from pathlib import Path
import PyPDF2

from tools.embedding_tool import get_embedding
from tools.supabase_tool import _client


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extracts all text from a PDF file."""
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"[PDF Tool] Error reading PDF {file_path}: {e}")
    return text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Splits a long text into overlapping chunks for better semantic retrieval."""
    words = text.split()
    chunks = []
    
    # Convert token limits roughly to words (1 token ~= 0.75 words)
    # Using simple word count for speed here instead of full tiktoken
    words_per_chunk = int(chunk_size * 0.75)
    words_overlap = int(overlap * 0.75)
    
    i = 0
    while i < len(words):
        chunk_words = words[i : i + words_per_chunk]
        chunks.append(" ".join(chunk_words))
        i += (words_per_chunk - words_overlap)
        
    return chunks


def ingest_pdf_to_knowledge_base(file_path: str | Path, description: str = ""):
    """
    Complete pipeline: Read PDF -> Extract Text -> Chunk -> Auto-Embed -> Supabase
    """
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {path}")
        return False
        
    print(f"\n[Knowledge Base] Ingesting {path.name}...")
    
    # 1. Create file record in Supabase
    file_record = _client().table("organizer_files").insert({
        "filename": path.name,
        "description": description,
        "status": "processing"
    }).execute()
    
    file_id = file_record.data[0]["id"]
    
    # 2. Extract and Chunk
    text = extract_text_from_pdf(path)
    if not text.strip():
        print(f"❌ Failed to extract text or PDF is empty.")
        _client().table("organizer_files").update({"status": "failed"}).eq("id", file_id).execute()
        return False
        
    chunks = chunk_text(text)
    print(f"  -> Extracted {len(text)} characters, split into {len(chunks)} chunks.")
    
    # 3. Embed and Store
    inserted_count = 0
    for i, chunk in enumerate(chunks):
        try:
            print(f"  -> Embedding chunk {i+1}/{len(chunks)}...")
            vector = get_embedding(chunk)
            
            _client().table("event_knowledge_chunks").insert({
                "file_id": file_id,
                "chunk_index": i,
                "content": chunk,
                "embedding": vector
            }).execute()
            inserted_count += 1
        except Exception as e:
            print(f"⚠️ Error embedding chunk {i+1}: {e}")
            
    # 4. Mark success
    _client().table("organizer_files").update({"status": "processed"}).eq("id", file_id).execute()
    print(f"✅ Successfully ingested {inserted_count} chunks into the Knowledge Base!")
    return True


if __name__ == "__main__":
    # Test script usage
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m tools.pdf_ingestion_tool <path_to_pdf>")
    else:
        # Requires PyPDF2 to be installed
        try:
            import PyPDF2
        except ImportError:
            print("Please install PyPDF2 first: pip install PyPDF2")
            sys.exit(1)
            
        ingest_pdf_to_knowledge_base(sys.argv[1])
