from anthropic import Anthropic

from src.parsing.vision_router import keyword_hit

SUMMARY_MODEL = "claude-sonnet-5"
# 60000자였을 때 큰 문서(예: AD9361 UG-570, candidate 44페이지)에서 실제로 한도에 걸려
# 뒤쪽 페이지(타이밍 다이어그램 포함)가 통째로 잘려나간 사례가 있었다. Sonnet 컨텍스트
# 대비 여유가 충분하므로 넉넉히 올린다.
MAX_CANDIDATE_CHARS = 180000
SUMMARY_MAX_TOKENS = 8192

SUMMARY_TOOL = {
    "name": "emit_timing_summary",
    "description": "데이터시트에서 추출한 타이밍 파라미터와 타이밍 다이어그램 설명을 구조화해서 반환한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "parameters": {
                "type": "array",
                "description": "타이밍 파라미터 표 (setup/hold time 등)",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "예: tSU, tHD"},
                        "name": {"type": "string", "description": "파라미터 이름/설명"},
                        "min": {"type": "string"},
                        "typ": {"type": "string"},
                        "max": {"type": "string"},
                        "unit": {"type": "string"},
                        "page": {"type": "integer"},
                    },
                    "required": ["name"],
                },
            },
            "diagrams": {
                "type": "array",
                "description": "타이밍 다이어그램/시퀀스 설명",
                "items": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "title": {"type": "string"},
                        "description": {"type": "string", "description": "신호 전이 순서, 인과관계를 포함한 설명"},
                    },
                    "required": ["page", "description"],
                },
            },
        },
        "required": ["parameters", "diagrams"],
    },
}

SUMMARY_INSTRUCTION = """다음은 한 반도체 칩 데이터시트에서 타이밍 관련 내용으로 판별된 페이지 발췌다.
이 내용만 근거로 emit_timing_summary 도구를 호출해 다음을 구조화하라.
- parameters: 표에 등장하는 타이밍 파라미터(setup/hold time, 클럭 주기 등)를 기호/이름/min/typ/max/unit/페이지 단위로 정리
- diagrams: 타이밍 다이어그램/시퀀스가 설명하는 신호 전이 순서와 인과관계를 페이지별로 요약
발췌에 없는 내용은 만들어내지 말고, 해당 항목을 비워둔다."""


def select_candidate_pages(documents: list[dict]) -> list[dict]:
    return [d for d in documents if d["used_vision"] or keyword_hit(d["text"])]


def summarize_timing(documents: list[dict]) -> dict:
    candidates = select_candidate_pages(documents)
    if not candidates:
        return {"parameters": [], "diagrams": []}

    combined = "\n\n".join(f"[p.{d['page_number']}]\n{d['text']}" for d in candidates)[:MAX_CANDIDATE_CHARS]

    client = Anthropic()
    response = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=SUMMARY_MAX_TOKENS,
        tools=[SUMMARY_TOOL],
        tool_choice={"type": "tool", "name": "emit_timing_summary"},
        messages=[{"role": "user", "content": f"{SUMMARY_INSTRUCTION}\n\n{combined}"}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    print(f"[timing_summary] tool_use 블록을 찾지 못함 (stop_reason={response.stop_reason})")
    return {"parameters": [], "diagrams": []}
