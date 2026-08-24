import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.analysis.timing_summary import summarize_timing
from src.parsing.pipeline import build_page_documents
from src.parsing.tier2_vision import render_page_to_png_bytes
from src.vectordb.build_index import index_documents

load_dotenv(PROJECT_ROOT / ".env")

UPLOAD_DIR = PROJECT_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
UPLOAD_CHROMA_DIR = PROJECT_ROOT / "chroma_db_uploads"
QUERY_LOG_PATH = PROJECT_ROOT / "query_log.jsonl"

st.set_page_config(page_title="Datasheet Timing Summary", layout="wide")
st.title("데이터시트 타이밍 요약")

tab_summary, tab_chat = st.tabs(["데이터시트 요약", "질의응답 (베타)"])

with tab_summary:
    uploaded_files = st.file_uploader(
        "데이터시트 PDF를 올려주세요 (파일 선택 또는 드래그 앤 드롭, 여러 개 가능)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    for uploaded_file in uploaded_files or []:
        file_bytes = uploaded_file.getvalue()
        file_hash = hashlib.sha1(file_bytes).hexdigest()[:10]
        pdf_path = UPLOAD_DIR / f"{file_hash}_{uploaded_file.name}"
        if not pdf_path.exists():
            pdf_path.write_bytes(file_bytes)

        cache_key = f"summary_{file_hash}"
        if cache_key not in st.session_state:
            with st.spinner(f"{uploaded_file.name} 분석 중 (파싱 → 벡터DB 저장 → 타이밍 요약)..."):
                documents = build_page_documents(str(pdf_path))
                chunk_count = index_documents(documents, str(UPLOAD_CHROMA_DIR), collection_name=file_hash)
                summary = summarize_timing(documents)
                st.session_state[cache_key] = {
                    "documents": documents,
                    "summary": summary,
                    "chunk_count": chunk_count,
                }

        data = st.session_state[cache_key]
        documents, summary = data["documents"], data["summary"]
        vision_pages = sum(1 for d in documents if d["used_vision"])

        st.markdown(f"## {uploaded_file.name}")
        col1, col2, col3 = st.columns(3)
        col1.metric("총 페이지", len(documents))
        col2.metric("Vision 분석 페이지", vision_pages)
        col3.metric("벡터DB 청크", data["chunk_count"])

        st.markdown("#### 타이밍 파라미터")
        params = summary.get("parameters", [])
        if params:
            st.dataframe(pd.DataFrame(params), use_container_width=True, hide_index=True)
        else:
            st.info("추출된 타이밍 파라미터가 없습니다.")

        st.markdown("#### 타이밍 다이어그램")
        diagrams = summary.get("diagrams", [])
        if not diagrams:
            st.info("타이밍 다이어그램으로 판별된 페이지가 없습니다.")
        for diagram in diagrams:
            page_number = diagram.get("page")
            title = diagram.get("title") or f"p.{page_number}"
            with st.expander(f"p.{page_number} — {title}"):
                img_col, text_col = st.columns([1, 1])
                with img_col:
                    if page_number:
                        try:
                            st.image(render_page_to_png_bytes(str(pdf_path), page_number), use_container_width=True)
                        except Exception:
                            st.caption("페이지 이미지를 불러오지 못했습니다.")
                with text_col:
                    st.write(diagram.get("description", ""))

        st.divider()

with tab_chat:
    st.caption("후순위 기능: 여러 데이터시트를 미리 인덱싱해둔 공용 벡터DB에 질의합니다 (`python -m src.vectordb.build_index`로 생성).")
    from src.agent.agent import DatasheetAgent

    @st.cache_resource
    def get_agent() -> "DatasheetAgent":
        return DatasheetAgent()

    question = st.text_input("질문을 입력하세요 (예: 이 칩의 리셋 시퀀스는?)")
    if st.button("질문하기") and question:
        with st.spinner("검색 중..."):
            result = get_agent().ask(question)
        st.markdown("### 답변")
        st.write(result["answer"])
        st.caption(f"응답 시간: {result['latency']:.2f}초")
        st.markdown("### 참고 출처")
        for src in result["sources"]:
            st.write(f"- {src['source']} (p.{src['page_number']})")

    if QUERY_LOG_PATH.exists():
        records = [json.loads(line) for line in QUERY_LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        if records:
            df = pd.DataFrame(records)
            all_sources = [s["source"] for r in records for s in r["sources"]]
            top_sources = pd.Series(all_sources).value_counts().head(10)

            st.markdown("### 통계")
            c1, c2, c3 = st.columns(3)
            c1.metric("총 질의 수", len(df))
            c2.metric("평균 응답 시간(초)", f"{df['latency'].mean():.2f}")
            c3.metric("가장 많이 인용된 문서", top_sources.index[0] if len(top_sources) else "-")
            st.bar_chart(top_sources)
            st.dataframe(df[["question", "latency"]].tail(20))
