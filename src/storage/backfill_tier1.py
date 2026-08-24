import argparse
from pathlib import Path

from src.parsing.pipeline import PIPELINE_VERSION
from src.parsing.tier1_tables import extract_tables_per_page, table_to_markdown
from src.storage import page_cache


def backfill_tier1_for_file(pdf_path: str) -> int:
    """tier1_tables 컬럼이 생기기 전에 캐시된 행에 Tier1(표) 결과만 로컬에서 다시 뽑아
    채워넣는다. Tier0 텍스트와 Tier2 Vision 설명은 이미 저장된 값을 그대로 재사용하므로
    API 호출이 전혀 발생하지 않는다."""
    source_name = Path(pdf_path).name
    missing = page_cache.get_pages_missing_tier1(source_name, PIPELINE_VERSION)
    if not missing:
        return 0

    tables_by_page = extract_tables_per_page(pdf_path)

    for row in missing:
        page_number = row["page_number"]
        tier1_markdown = "\n\n".join(table_to_markdown(t) for t in tables_by_page.get(page_number, []))

        parts = [row["tier0_text"].strip()] if row["tier0_text"] else []
        if tier1_markdown.strip():
            parts.append(tier1_markdown)
        if row["vision_description"]:
            parts.append(f"[Vision 추출: 타이밍 다이어그램 설명]\n{row['vision_description']}")
        combined = "\n\n".join(p for p in parts if p.strip())

        page_cache.update_tier1(source_name, page_number, PIPELINE_VERSION, tier1_markdown, combined)

    return len(missing)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_paths", nargs="+", help="백필할 PDF 파일 경로들")
    args = parser.parse_args()
    for path in args.pdf_paths:
        count = backfill_tier1_for_file(path)
        print(f"{Path(path).name}: {count}개 행 백필 완료")
