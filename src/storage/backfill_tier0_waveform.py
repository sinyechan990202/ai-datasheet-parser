import argparse
from pathlib import Path

from src.parsing.pipeline import PIPELINE_VERSION
from src.parsing.tier0_text import extract_ascii_waveforms
from src.storage import page_cache


def backfill_tier0_waveform_for_file(pdf_path: str) -> int:
    """tier0_waveform_ascii 컬럼이 생기기 전에 캐시된 행에 좌표 기반 ASCII 파형 재구성 결과를
    채워넣는다. 로컬 연산만 하므로 API 호출은 발생하지 않는다."""
    source_name = Path(pdf_path).name
    missing_pages = page_cache.get_pages_missing_tier0_waveform_ascii(source_name, PIPELINE_VERSION)
    if not missing_pages:
        return 0

    waveform_by_page = extract_ascii_waveforms(pdf_path)
    for page_number in missing_pages:
        page_cache.update_tier0_waveform_ascii(
            source_name, page_number, PIPELINE_VERSION, waveform_by_page.get(page_number, "")
        )

    return len(missing_pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_paths", nargs="+", help="백필할 PDF 파일 경로들")
    args = parser.parse_args()
    for path in args.pdf_paths:
        count = backfill_tier0_waveform_for_file(path)
        print(f"{Path(path).name}: {count}개 행 백필 완료")
