# pyright: reportMissingImports=false
import os
import sys
import logging
from typing import List
from pathlib import Path

# Ensure project root is on path so 'server.prompt_templates' resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import Ollama

BASE_DIR        = Path(__file__).resolve().parent
DB_FOLDER       = BASE_DIR / "restaurant_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL       = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
RETRIEVAL_K     = 3
MAX_CONTEXT_CHARS = 2000

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RestaurantRAG:
    """Restaurant RAG System — retrieves relevant docs then queries Ollama directly."""

    def __init__(self, db_folder: str = DB_FOLDER, llm_model: str = LLM_MODEL):
        self.db_folder = str(db_folder)
        self.llm_model = llm_model
        self.db        = None
        self.llm       = None
        self.retriever = None

        try:
            self._initialize()
            logger.info("✅ RAG System initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG: {e}")
            raise

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def _initialize(self):
        # 1. Embeddings
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"}
        )

        # 2. Vector DB
        if not Path(self.db_folder).exists():
            raise FileNotFoundError(
                f"Vector database not found at '{self.db_folder}'\n"
                "Run 'python indexer.py' first to create the database."
            )

        logger.info(f"Loading vector database from '{self.db_folder}'")
        self.db = Chroma(
            persist_directory=self.db_folder,
            embedding_function=embedding_model
        )
        logger.info(f"Database loaded with {self.db._collection.count()} documents")

        # 3. LLM — plain Ollama client, returns a string on .invoke()
        logger.info(f"Loading LLM: {self.llm_model}")
        self.llm = Ollama(model=self.llm_model, temperature=0.2)

        # 4. Retriever
        self.retriever = self.db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": RETRIEVAL_K}
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve_documents(self, query: str, k: int = RETRIEVAL_K) -> List:
        """Return raw LangChain Document objects for a query."""
        try:
            results = self.db.similarity_search(query, k=k)
            logger.debug(f"Retrieved {len(results)} documents for: {query}")
            return results
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []

    def answer_question(self, question: str) -> dict:
        """
        Full RAG pipeline:
          1. Retrieve top-k docs
          2. Build prompt via build_system_prompt
          3. Call Ollama directly (returns a plain string)
          4. Return structured dict
        """
        try:
            logger.info(f"Processing question: {question}")

            # Step 1 — retrieve
            docs = self.retriever.invoke(question)
            def format_docs(docs):
                formatted = []
                for i, d in enumerate(docs, 1):
                    formatted.append(f"[DOC {i}]\n{d.page_content}")
                return "\n\n".join(formatted)

            retrieved_context = format_docs(docs)

            # Step 2 — build prompt
            from server.prompt_templates import build_system_prompt
            prompt_text = build_system_prompt(
                memory={},
                stage="general",
                user_data={},
                retrieved_context=retrieved_context,
            )

            # Step 3 — call LLM; Ollama.invoke() always returns a plain string
            full_prompt = f"{prompt_text}\n\nQuestion: {question}\nAnswer:"
            raw = self.llm.invoke(full_prompt)

            # Defensive: coerce to string regardless of LangChain version quirks
            answer = raw if isinstance(raw, str) else str(raw)

            # Step 4 — return structured result
            return {
                "answer": answer.strip(),
                "sources": [
                    {
                        "source":  doc.metadata.get("source", "Unknown"),
                        "content": doc.page_content[:MAX_CONTEXT_CHARS],
                    }
                    for doc in docs
                ]
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {"answer": f"Error: {str(e)}", "sources": []}

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def display_results(self, query: str, k: int = RETRIEVAL_K, show_llm: bool = True):
        """Pretty-print retrieval results and optionally the LLM answer."""
        print("\n" + "=" * 70)
        print(f"Query: {query}")
        print("=" * 70)

        documents = self.retrieve_documents(query, k=k)
        if not documents:
            print("⚠️  No relevant documents found")
            return

        print(f"\n📚 Retrieved {len(documents)} document(s):\n")
        for i, doc in enumerate(documents, 1):
            print(f"Result {i}")
            print(f"Source: {doc.metadata.get('source', 'Unknown')}")
            print(f"Preview: {doc.page_content[:300]}...")
            print("-" * 70)

        if show_llm:
            print("\n🤖 AI Answer:\n")
            result = self.answer_question(query)
            print(result["answer"])
            print("\n📖 Sources Used:")
            for src in result["sources"]:
                print(f"  - {src['source']}")
            print("=" * 70)

    def run_interactive(self):
        """Interactive Q&A loop."""
        print("\n" + "=" * 70)
        print("🍽️  La Bella Tavola Restaurant RAG System")
        print("=" * 70)
        print("Commands:")
        print("  - Type any question to get help")
        print("  - Type 'retrieve <question>' to see only retrieved documents")
        print("  - Type 'exit' to quit")
        print("=" * 70)

        while True:
            try:
                user_input = input("\n🔍 Ask a question: ").strip()
                if not user_input:
                    continue
                if user_input.lower() == "exit":
                    print("\n👋 Goodbye!")
                    break
                if user_input.lower().startswith("retrieve "):
                    self.display_results(user_input[9:].strip(), show_llm=False)
                else:
                    self.display_results(user_input, show_llm=True)
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"❌ An error occurred: {e}")


def main():
    try:
        rag = RestaurantRAG()
        rag.run_interactive()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main()