import base64

import pymupdf as fitz
from anthropic import Anthropic

VISION_MODEL = "claude-haiku-4-5-20251001"

VISION_PROMPT = """이 이미지는 반도체/칩 데이터시트의 한 페이지이며, 타이밍 다이어그램 또는 파형을 포함할 가능성이 있다고 판별되었습니다.
페이지에 포함된 타이밍 다이어그램/파형을 다음 관점에서 텍스트로 상세히 설명하세요.
- 등장하는 신호 이름과 상태 전이 순서
- 표시된 타이밍 파라미터(setup/hold time 등)의 이름과 값
- 신호 간 인과관계 (예: 클럭 rising edge 이후 데이터 valid 시점)
표나 목록 형태로 정리해서 답하고, 타이밍 관련 내용이 없다면 "타이밍 관련 내용 없음"이라고만 답하세요."""


def render_page_to_png_bytes(pdf_path: str, page_number: int, zoom: float = 2.0) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def describe_page_with_vision(pdf_path: str, page_number: int, model: str = VISION_MODEL) -> str:
    client = Anthropic()
    image_b64 = base64.standard_b64encode(render_page_to_png_bytes(pdf_path, page_number)).decode("utf-8")
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )
    return "".join(block.text for block in message.content if block.type == "text")
