import json
import time
from pathlib import Path

import chromadb
from anthropic import Anthropic

from src.vectordb.embed import embed_texts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERY_LOG_PATH = PROJECT_ROOT / "query_log.jsonl"
AGENT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """당신은 반도체/칩 데이터시트 검색을 돕는 엔지니어링 어시스턴트입니다.
search_datasheets 도구로 검색된 내용만 근거로 답변하고, 답변 끝에 참고한 출처(파일명, 페이지 번호)를 명시하세요.
검색 결과에 없는 내용은 추측하지 말고 모른다고 답하세요."""

TOOLS = [
    {
        "name": "search_datasheets",
        "description": "인덱싱된 데이터시트에서 질문과 관련된 내용을 검색한다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 질문 또는 키워드"},
                "top_k": {"type": "integer", "description": "검색할 결과 개수", "default": 4},
            },
            "required": ["query"],
        },
    }
]


class DatasheetAgent:
    def __init__(self, persist_dir: str | Path = PROJECT_ROOT / "chroma_db", collection_name: str = "datasheets", model: str = AGENT_MODEL):
        self.client = Anthropic()
        self.model = model
        self.collection = chromadb.PersistentClient(path=str(persist_dir)).get_or_create_collection(collection_name)

    def _search(self, query: str, top_k: int = 4) -> list[dict]:
        results = self.collection.query(query_embeddings=embed_texts([query]), n_results=top_k)
        return [
            {"text": doc, "source": meta["source"], "page_number": meta["page_number"]}
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]

    def ask(self, question: str) -> dict:
        start = time.time()
        messages = [{"role": "user", "content": question}]
        response = self.client.messages.create(
            model=self.model, max_tokens=1024, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
        )

        retrieved_sources = []
        while response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "search_datasheets":
                    hits = self._search(block.input["query"], block.input.get("top_k", 4))
                    retrieved_sources.extend(hits)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(hits, ensure_ascii=False),
                    })
            messages.append({"role": "user", "content": tool_results})
            response = self.client.messages.create(
                model=self.model, max_tokens=1024, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
            )

        answer = "".join(block.text for block in response.content if block.type == "text")
        latency = time.time() - start
        self._log_query(question, answer, retrieved_sources, latency)
        return {"answer": answer, "sources": retrieved_sources, "latency": latency}

    def _log_query(self, question: str, answer: str, sources: list[dict], latency: float) -> None:
        record = {
            "timestamp": time.time(),
            "question": question,
            "answer": answer,
            "sources": [{"source": s["source"], "page_number": s["page_number"]} for s in sources],
            "latency": latency,
        }
        with open(QUERY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
