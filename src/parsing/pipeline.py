from pathlib import Path

import pymupdf as fitz

from src.parsing.tier1_tables import extract_tables_per_page, table_to_markdown
from src.parsing.tier2_vision import describe_page_with_vision
from src.parsing.vision_router import classify_page, compute_document_thresholds
from src.storage import page_cache

# 라우팅/프롬프트 로직을 바꿀 때마다 올린다. 캐시 키에 포함되므로, 버전을 올리면
# 예전 로직으로 저장된 캐시는 자동으로 무시되고 새 로직으로 다시 파싱된다 —
# 로직이 바뀐 뒤에도 옛날 캐시를 그대로 믿어버리는 사고를 방지한다.
PIPELINE_VERSION = "router-v4-relative-threshold"


def build_page_documents(pdf_path: str, force: bool = False, force_pages: set[int] | None = None) -> list[dict]:
    """PDF를 페이지 단위로 파싱한다. 이미 같은 (파일, 페이지, PIPELINE_VERSION)로 파싱한
    적이 있으면 캐시(parse_cache.sqlite3)에서 읽어오고, Tier0~2를 다시 돌리지 않는다.

    force=True면 이 파일 전체를 강제로 재파싱한다.
    force_pages={101}처럼 페이지 번호 집합을 주면 그 페이지들만 강제로 재파싱한다
    (라우팅/프롬프트를 조금 고치고 특정 페이지 품질만 확인해보고 싶을 때 사용)."""
    force_pages = force_pages or set()
    source_name = Path(pdf_path).name
    doc = fitz.open(pdf_path)
    thresholds = compute_document_thresholds(doc)
    tables_by_page = extract_tables_per_page(pdf_path)

    documents = []
    for i, page in enumerate(doc):
        page_number = i + 1

        if not force and page_number not in force_pages:
            cached = page_cache.get(source_name, page_number, PIPELINE_VERSION)
            if cached:
                documents.append(cached)
                continue

        text = page.get_text("text")
        tier1_markdown = "\n\n".join(table_to_markdown(table) for table in tables_by_page.get(page_number, []))

        parts = [text.strip()]
        if tier1_markdown.strip():
            parts.append(tier1_markdown)

        used_vision, reason = classify_page(page, thresholds)
        vision_text = None
        if used_vision:
            vision_text = describe_page_with_vision(pdf_path, page_number)
            parts.append(f"[Vision 추출: 타이밍 다이어그램 설명]\n{vision_text}")

        combined = "\n\n".join(part for part in parts if part.strip())
        if not combined.strip():
            continue

        page_cache.save(
            source_file=source_name,
            page_number=page_number,
            pipeline_version=PIPELINE_VERSION,
            tier0_text=text,
            tier1_tables=tier1_markdown,
            router_reason=reason,
            used_vision=used_vision,
            vision_description=vision_text,
            combined_text=combined,
        )
        documents.append({
            "source": source_name,
            "page_number": page_number,
            "text": combined,
            "used_vision": used_vision,
        })

    doc.close()
    return documents


def build_documents_for_folder(folder: str) -> list[dict]:
    all_docs = []
    for pdf_path in sorted(Path(folder).rglob("*.pdf")):
        print(f"[parsing] {pdf_path.relative_to(folder)}")
        all_docs.extend(build_page_documents(str(pdf_path)))
    return all_docs
