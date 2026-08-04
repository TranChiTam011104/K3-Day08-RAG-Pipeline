"""Task 4 - Chunking and indexing markdown documents into ChromaDB.

Theo README của bài lab:
- Chunking: RecursiveCharacterTextSplitter.
- Embedding: OpenAI text-embedding-3-small khi có API key.
- Vector store: ChromaDB persistent, cosine similarity.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# =============================================================================
# PROJECT PATHS AND ENVIRONMENT
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
# File chuẩn nằm trong src/. Nhánh else giúp file vẫn chạy được khi đặt ở project root.
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "src" else SCRIPT_DIR
ENV_FILE = PROJECT_ROOT / ".env"

# Nạp đúng file .env ở project root, không phụ thuộc terminal đang đứng ở đâu.
load_dotenv(dotenv_path=ENV_FILE, override=False)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STANDARDIZED_DIR = PROJECT_ROOT / "data" / "standardized"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"


# =============================================================================
# CONFIGURATION
# =============================================================================

# RecursiveCharacterTextSplitter là lựa chọn mặc định, an toàn với Markdown có
# cấu trúc không đồng đều. 800 ký tự giữ đủ ngữ cảnh cho một đoạn chính sách;
# overlap 100 ký tự giúp hạn chế mất ý ở ranh giới giữa hai chunk.
CHUNKING_METHOD = "recursive"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# README cho phép dùng OpenAI text-embedding-3-small khi có API key.
# Dimension mặc định của model là 1536; khai báo rõ để Task 5 dùng nhất quán.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
EMBEDDING_BATCH_SIZE = 100

VECTOR_STORE = "chromadb"
COLLECTION_NAME = "university_services_docs"


# =============================================================================
# HELPERS
# =============================================================================

def _require_openai_api_key() -> str:
    """Lấy OPENAI_API_KEY từ .env và báo lỗi rõ ràng nếu thiếu."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            f"Không tìm thấy OPENAI_API_KEY. Hãy thêm key vào: {ENV_FILE}\n"
            "Ví dụ: OPENAI_API_KEY=sk-..."
        )
    return api_key


def _chunk_id(chunk: dict[str, Any]) -> str:
    """Tạo ID ổn định và không trùng, kể cả khi hai thư mục có cùng tên file."""
    metadata = chunk["metadata"]
    raw_id = f"{metadata['source_path']}::chunk::{metadata['chunk_index']}"
    digest = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:16]
    return f"chunk-{digest}"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict[str, Any]]:
    """Đọc toàn bộ file Markdown trong data/standardized/.

    Returns:
        Danh sách document theo format:
        {"content": str, "metadata": {"source": str, "source_path": str,
        "type": str}}
    """
    if not STANDARDIZED_DIR.exists():
        print(f"[!] Không tìm thấy thư mục: {STANDARDIZED_DIR}")
        return []

    documents: list[dict[str, Any]] = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if not md_file.is_file():
            continue

        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            print(f"[!] Bỏ qua file rỗng: {md_file}")
            continue

        relative_path = md_file.relative_to(STANDARDIZED_DIR)
        top_level_dir = relative_path.parts[0].lower() if len(relative_path.parts) > 1 else "other"
        doc_type = top_level_dir if top_level_dir in {"legal", "news"} else "other"

        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "source_path": relative_path.as_posix(),
                    "type": doc_type,
                },
            }
        )

    return documents


def chunk_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tách documents bằng RecursiveCharacterTextSplitter.

    Returns:
        Danh sách chunk theo format:
        {"content": str, "metadata": dict}
    """
    if not documents:
        return []

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise ImportError(
            "Thiếu langchain-text-splitters. Cài bằng lệnh: "
            "pip install langchain-text-splitters"
        ) from exc

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )

    chunks: list[dict[str, Any]] = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for chunk_index, chunk_text in enumerate(splits):
            cleaned_text = chunk_text.strip()
            if not cleaned_text:
                continue

            chunks.append(
                {
                    "content": cleaned_text,
                    "metadata": {
                        **doc["metadata"],
                        "chunk_index": chunk_index,
                        "chunking_method": CHUNKING_METHOD,
                        "chunk_size": CHUNK_SIZE,
                        "chunk_overlap": CHUNK_OVERLAP,
                    },
                }
            )

    return chunks


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tạo embedding cho toàn bộ chunks bằng OpenAI API.

    API key được đọc từ OPENAI_API_KEY trong file .env ở project root.

    Returns:
        Chính danh sách chunks, mỗi phần tử được thêm key ``embedding``.
    """
    if not chunks:
        return []

    api_key = _require_openai_api_key()

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("Thiếu openai. Cài bằng lệnh: pip install openai") from exc

    # OPENAI_BASE_URL là tùy chọn cho endpoint tương thích OpenAI. Không tự động
    # dùng OPENROUTER_API_KEY vì README yêu cầu OpenAI embedding API.
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    client = OpenAI(api_key=api_key, base_url=base_url)

    texts = [chunk["content"] for chunk in chunks]
    all_embeddings: list[list[float]] = []

    print(
        f"[i] Tạo embedding bằng {EMBEDDING_MODEL} "
        f"(dim={EMBEDDING_DIM}) cho {len(texts)} chunks..."
    )

    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch_texts = texts[start : start + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch_texts,
            dimensions=EMBEDDING_DIM,
            encoding_format="float",
        )

        # Dùng index trong response để bảo toàn đúng thứ tự input.
        response_items = sorted(response.data, key=lambda item: item.index)
        batch_embeddings = [item.embedding for item in response_items]

        if len(batch_embeddings) != len(batch_texts):
            raise RuntimeError(
                "Số embedding trả về không khớp số chunk trong batch: "
                f"{len(batch_embeddings)} != {len(batch_texts)}"
            )

        for embedding in batch_embeddings:
            if len(embedding) != EMBEDDING_DIM:
                raise RuntimeError(
                    "Embedding dimension không đúng: "
                    f"nhận {len(embedding)}, kỳ vọng {EMBEDDING_DIM}"
                )

        all_embeddings.extend(batch_embeddings)
        print(f"[i] Đã embed {min(start + len(batch_texts), len(texts))}/{len(texts)} chunks")

    for chunk, embedding in zip(chunks, all_embeddings, strict=True):
        chunk["embedding"] = embedding

    return chunks


def index_to_vectorstore(chunks: list[dict[str, Any]]) -> int:
    """Ghi chunks, embeddings và metadata vào ChromaDB persistent.

    Collection được tạo lại mỗi lần chạy để không giữ dữ liệu cũ hoặc tạo
    duplicate khi re-index. Cosine distance được dùng cho semantic search ở Task 5.

    Returns:
        Số chunks đã index.
    """
    if not chunks:
        print("[!] Không có chunk để index.")
        return 0

    missing_embeddings = [i for i, chunk in enumerate(chunks) if "embedding" not in chunk]
    if missing_embeddings:
        raise ValueError(
            "Một số chunks chưa có embedding. Hãy gọi embed_chunks() trước. "
            f"Ví dụ index lỗi đầu tiên: {missing_embeddings[0]}"
        )

    try:
        import chromadb
    except ImportError as exc:
        raise ImportError("Thiếu chromadb. Cài bằng lệnh: pip install chromadb") from exc

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Rebuild collection để kết quả phản ánh đúng toàn bộ documents hiện tại.
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        # Collection chưa tồn tại ở lần chạy đầu tiên.
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIM,
            "chunking_method": CHUNKING_METHOD,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
        },
    )

    ids = [_chunk_id(chunk) for chunk in chunks]
    documents = [chunk["content"] for chunk in chunks]
    embeddings = [chunk["embedding"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    indexed_count = collection.count()
    if indexed_count != len(chunks):
        raise RuntimeError(
            "Index chưa đầy đủ: "
            f"ChromaDB có {indexed_count} chunks, kỳ vọng {len(chunks)}"
        )

    print(f"[OK] Đã index {indexed_count} chunks vào: {CHROMA_DIR}")
    return indexed_count


def run_pipeline() -> int:
    """Chạy pipeline Task 4: load -> chunk -> embed -> index."""
    print("=" * 64)
    print("Task 4: Chunking & Indexing")
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Input        : {STANDARDIZED_DIR}")
    print(f"  .env         : {ENV_FILE}")
    print(f"  Chunking     : {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding    : {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector store : {VECTOR_STORE} / cosine")
    print("=" * 64)

    documents = load_documents()
    if not documents:
        raise RuntimeError(
            f"Không có file Markdown để index trong {STANDARDIZED_DIR}. "
            "Hãy chạy Task 3 trước."
        )
    print(f"[OK] Loaded {len(documents)} documents")

    chunks = chunk_documents(documents)
    if not chunks:
        raise RuntimeError("Chunking không tạo ra chunk nào.")
    print(f"[OK] Created {len(chunks)} chunks")

    embedded_chunks = embed_chunks(chunks)
    print(f"[OK] Embedded {len(embedded_chunks)} chunks")

    indexed_count = index_to_vectorstore(embedded_chunks)
    print("[OK] Task 4 hoàn tất")
    return indexed_count


if __name__ == "__main__":
    run_pipeline()