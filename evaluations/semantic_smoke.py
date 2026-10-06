"""Run with python -m evaluations.semantic_smoke (downloads MiniLM on first run)."""
from langchain_core.documents import Document
from src.pdf_rag.retrieval import PdfIndex


def main():
    index = PdfIndex.from_documents([
        Document(page_content="A physician treats patients at a hospital."),
        Document(page_content="Ethernet transmits frames over a computer network."),
        Document(page_content="Oranges grow on trees."),
    ], backend="semantic")
    try:
        top = index.retrieve("What does a doctor do?")[0]
        assert "physician" in top.page_content, top.page_content
        print("PASS: semantic paraphrase retrieval with real MiniLM embeddings")
    finally:
        index.close()


if __name__ == "__main__":
    main()
