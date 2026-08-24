import argparse
from pathlib import Path

from src.parsing.pipeline import PIPELINE_VERSION
from src.parsing.tier0_text import extract_raw_shapes
from src.storage import page_cache


def backfill_tier0_shapes_for_file(pdf_path: str) -> int:
    """tier0_shapes 컬럼이 생기기 전에 캐시된 행에 원시 도형 덤프(노이즈 제거 없음)를
    채워넣는다. 로컬 연산만 하므로 API 호출은 발생하지 않는다."""
    source_name = Path(pdf_path).name
    missing_pages = page_cache.get_pages_missing_tier0_shapes(source_name, PIPELINE_VERSION)
    if not missing_pages:
        return 0

    shapes_by_page = extract_raw_shapes(pdf_path)
    for page_number in missing_pages:
        page_cache.update_tier0_shapes(source_name, page_number, PIPELINE_VERSION, shapes_by_page.get(page_number, ""))

    return len(missing_pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_paths", nargs="+", help="백필할 PDF 파일 경로들")
    args = parser.parse_args()
    for path in args.pdf_paths:
        count = backfill_tier0_shapes_for_file(path)
        print(f"{Path(path).name}: {count}개 행 백필 완료")
