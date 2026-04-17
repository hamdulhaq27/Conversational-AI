import os
import logging
import shutil
from pathlib import Path
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from tqdm import tqdm

# Configuration
DOC_FOLDER = "../docs/restaurant_docs"  # Fixed path
DB_FOLDER = "restaurant_db"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 10

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_documents(folder: str) -> List:
    """Load all .txt files from folder with error handling."""
    documents = []

    if not os.path.exists(folder):
        logger.error(f"Document folder not found: {folder}")
        raise FileNotFoundError(f"Document folder '{folder}' does not exist")

    txt_files = [f for f in os.listdir(folder) if f.endswith(".txt")]
    logger.info(f"Found {len(txt_files)} text files to process")

    for file in tqdm(txt_files, desc="Loading documents"):
        try:
            path = os.path.join(folder, file)
            loader = TextLoader(path, encoding="utf-8")
            docs = loader.load()

            # Add rich metadata
            for doc in docs:
                doc.metadata["source"] = file
                doc.metadata["file_path"] = path

            documents.extend(docs)
            logger.debug(f"Loaded: {file} ({len(docs)} documents)")

        except Exception as e:
            logger.warning(f"Failed to load {file}: {e}")
            continue

    logger.info(f"Total documents loaded: {len(documents)}")
    return documents


def chunk_documents(documents: List) -> List:
    """Split documents into chunks with overlap."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = splitter.split_documents(documents)
    logger.info(f"Total chunks created: {len(chunks)}")

    # Log chunk distribution
    avg_chunk_size = sum(len(chunk.page_content) for chunk in chunks) / len(chunks)
    logger.info(f"Average chunk size: {avg_chunk_size:.0f} characters")

    return chunks


def get_embedding_model():
    """Initialize embedding model with error handling."""
    try:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'}  # Explicit CPU usage
        )
        logger.info("Embedding model loaded successfully")
        return embedding_model
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        raise


def create_vector_db(chunks: List, embedding_model):
    """Create and persist vector database."""
    # Clean old database if exists
    if os.path.exists(DB_FOLDER):
        logger.info("Removing old database...")
        shutil.rmtree(DB_FOLDER)

    logger.info("Creating vector database...")

    try:
        db = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_model,
            persist_directory=DB_FOLDER
        )

        # Persistence is automatic in newer versions, but explicit call for compatibility
        db.persist()

        logger.info(f"Vector database created in '{DB_FOLDER}'")
        logger.info(f"Database size: {len(chunks)} chunks indexed")

        return db
    except Exception as e:
        logger.error(f"Failed to create vector database: {e}")
        raise


def main():
    """Main indexing pipeline."""
    try:
        logger.info("=" * 50)
        logger.info("Starting RAG Indexing Pipeline")
        logger.info("=" * 50)

        # Step 1: Load documents
        documents = load_documents(DOC_FOLDER)
        if not documents:
            logger.error("No documents loaded. Exiting.")
            return

        # Step 2: Chunk documents
        chunks = chunk_documents(documents)
        if not chunks:
            logger.error("No chunks created. Exiting.")
            return

        # Step 3: Load embedding model
        embedding_model = get_embedding_model()

        # Step 4: Create vector database
        db = create_vector_db(chunks, embedding_model)

        # Test retrieval
        test_query = "restaurant reservation policy"
        logger.info(f"\nTesting retrieval with query: '{test_query}'")
        results = db.similarity_search(test_query, k=3)
        logger.info(f"Retrieved {len(results)} results")
        for i, result in enumerate(results, 1):
            logger.info(f"  Result {i} - Source: {result.metadata['source']}")

        logger.info("=" * 50)
        logger.info("✅ RAG Indexing Pipeline Completed Successfully!")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
