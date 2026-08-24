import pymupdf as fitz


def extract_text_per_page(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pages.append({"page_number": i + 1, "text": page.get_text("text")})
    doc.close()
    return pages


def extract_raw_shapes(pdf_path: str) -> dict[int, str]:
    """벡터 드로잉 primitive(선/사각형/곡선)를 필터링 없이 그대로 덤프한다.
    표 테두리, 로고 등도 전혀 걸러내지 않은 원본 그대로 — 노이즈 제거는 의도적으로 하지 않았다."""
    doc = fitz.open(pdf_path)
    shapes_by_page = {}
    for i, page in enumerate(doc):
        raw_items = [str(item) for drawing in page.get_drawings() for item in drawing["items"]]
        shapes_by_page[i + 1] = "\n".join(raw_items)
    doc.close()
    return shapes_by_page
