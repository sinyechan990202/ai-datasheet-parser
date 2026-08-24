import argparse
from pathlib import Path

import chromadb

from src.parsing.pipeline import build_documents_for_folder
from src.vectordb.embed import embed_texts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNK_MAX_CHARS = 1500


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or [text]


def index_documents(documents: list[dict], persist_dir: str, collection_name: str) -> int:
    """documents를 청크로 쪼개 지정된 컬렉션에 저장한다. 컬렉션을 파일/문서 단위로
    분리해서 쓰면(예: 업로드 파일마다 고유 collection_name) 서로 다른 문서의 내용이
    검색 결과에 섞이지 않는다."""
    ids, texts, metadatas = [], [], []
    for doc in documents:
        for chunk_idx, chunk in enumerate(chunk_text(doc["text"])):
            ids.append(f"{doc['source']}::p{doc['page_number']}::c{chunk_idx}")
            texts.append(chunk)
            metadatas.append({
                "source": doc["source"],
                "page_number": doc["page_number"],
                "used_vision": doc["used_vision"],
            })

    if not texts:
        return 0

    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(collection_name)
    collection.upsert(ids=ids, embeddings=embed_texts(texts), documents=texts, metadatas=metadatas)
    return len(texts)


def build_index(data_dir: str, persist_dir: str, collection_name: str = "datasheets") -> None:
    documents = build_documents_for_folder(data_dir)
    if not documents:
        print(f"'{data_dir}'에서 PDF를 찾지 못했습니다.")
        return

    chunk_count = index_documents(documents, persist_dir, collection_name)
    vision_pages = sum(1 for d in documents if d["used_vision"])
    print(f"인덱싱 완료: 페이지 {len(documents)}개 (Vision 사용 {vision_pages}개), 청크 {chunk_count}개")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "datasheets"))
    parser.add_argument("--persist-dir", default=str(PROJECT_ROOT / "chroma_db"))
    parser.add_argument("--collection", default="datasheets")
    args = parser.parse_args()
    build_index(args.data_dir, args.persist_dir, args.collection)
