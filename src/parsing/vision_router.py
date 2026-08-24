import pymupdf as fitz
from anthropic import Anthropic

# 2~4글자 타이밍 기호(tH, tSU 등)는 "the", "with" 같은 일반 단어의 부분 문자열과 겹쳐
# 오탐이 심해 제외했다 — 실측 결과 p2~p31 중 20개 페이지가 "th" 하나 때문에 잘못 플래그됨.
# 데이터시트 표현이 통일되어 있지 않은 여러 벤더 문서에서도 안정적으로 걸리는
# 완전한 구(phrase) 단위 키워드만 남긴다.
TIMING_KEYWORDS = [
    "timing diagram", "timing chart", "timing waveform",
    "ac characteristics", "ac timing",
    "switching characteristics", "switching waveform",
    "read cycle", "write cycle", "read/write timing",
    "bus timing", "clock timing", "protocol timing", "serial timing",
    "waveform", "signal diagram",
    "타이밍도", "타이밍 다이어그램", "파형도", "신호 파형",
]

# 절대 임계값(drawings>100, text<900)은 이 10개 데이터시트에 맞춰 눈으로 보고 정한 값이었다.
# 실측해보니 같은 절대값이 문서마다 완전히 다른 상대적 위치에 해당했다(예: drawings=100이
# 어떤 문서에서는 상위 11%, 어떤 문서에서는 상위 64%) — 즉 이 숫자는 "이 벤더들이 벡터를
# 그리는 밀도"에 우연히 맞은 것이지 일반적인 기준이 아니다. 다른 벤더/포맷 문서에서는
# 다시 깨질 수 있으므로, 문서 자신의 페이지 분포에서 상대적 위치(percentile)로 기준을 잡는다.
TEXT_DENSITY_PERCENTILE = 0.5  # 이 percentile보다 텍스트가 적은 페이지 = 문서 내 "저밀도"
DRAWING_COUNT_PERCENTILE = 0.75  # 이 percentile보다 벡터 선분이 많은 페이지 = 문서 내 "그림 밀도 높음"
MIN_DRAWING_FLOOR = 20  # 벡터 그림이 거의 없는 문서에서 임계값이 0에 가깝게 무너지는 것을 방지

CLASSIFY_MODEL = "claude-haiku-4-5-20251001"
CLASSIFY_PROMPT = """다음은 반도체 데이터시트 한 페이지의 텍스트다. 이 페이지에 타이밍 다이어그램/파형
(신호의 시간에 따른 상태 전이, setup/hold time, 클럭 타이밍 시퀀스 등)이 포함되어 있거나 그런
그림을 직접 참조하고 있는가? 단순 성능 특성 그래프(전압/온도 대비 오차 등 시간축이 아닌 것),
핀 설명 표, 블록 다이어그램은 해당하지 않는다.
반드시 "YES" 또는 "NO" 한 단어로만 답하라.

텍스트:
{text}"""


def keyword_hit(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in TIMING_KEYWORDS)


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * pct))]


def compute_document_thresholds(doc: fitz.Document) -> dict[str, int]:
    """문서 자신의 페이지 분포에서 상대적 임계값을 계산한다. 문서마다 벡터 그림/텍스트
    밀도의 기본 수준이 다르므로, 절대 숫자 대신 이 문서 안에서 상대적으로 튀는 페이지를
    찾는다."""
    text_lens = [len(page.get_text("text").strip()) for page in doc]
    drawing_counts = [len(page.get_drawings()) for page in doc]
    return {
        "text_density": _percentile(text_lens, TEXT_DENSITY_PERCENTILE),
        "drawing_count": max(_percentile(drawing_counts, DRAWING_COUNT_PERCENTILE), MIN_DRAWING_FLOOR),
    }


def structural_signal(page: fitz.Page, drawing_count_threshold: int) -> bool:
    return len(page.get_drawings()) > drawing_count_threshold or bool(page.get_images())


def llm_confirms_timing(text: str) -> bool:
    client = Anthropic()
    response = client.messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=5,
        messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(text=text[:3000])}],
    )
    answer = "".join(block.text for block in response.content if block.type == "text").strip().upper()
    return answer.startswith("YES")


def classify_page(page: fitz.Page, thresholds: dict[str, int]) -> tuple[bool, str]:
    """(vision 필요 여부, 판단 근거)를 함께 반환한다. 근거 문자열은 캐시 DB에 같이
    저장해서, 왜 이 페이지가 이렇게 분류됐는지 나중에 DBeaver 등으로 바로 확인할 수 있게 한다."""
    text = page.get_text("text")
    low_density = len(text.strip()) < thresholds["text_density"]

    # 텍스트가 적은 페이지: keyword/구조 신호를 그대로 신뢰한다(실측상 신뢰도가 높았음).
    if low_density:
        if keyword_hit(text):
            return True, "keyword"
        if structural_signal(page, thresholds["drawing_count"]):
            return True, "structural_low_density"
        return False, "none"

    # 텍스트가 많아도 그림 밀도가 높으면 다이어그램이 본문과 같은 페이지에 있을 수 있다
    # (실제 사례: AD9361 UG-570 p.88 — 절차 설명 텍스트 밑에 Figure 60/61 타이밍 다이어그램이
    # 있었지만 텍스트 밀도 게이트에 걸려 누락됨). 이런 애매한 경우만 저비용 텍스트 분류로
    # 재확인한다 — 이미지가 아니라 텍스트만 보내므로 Tier2 Vision보다 훨씬 저렴하다.
    if structural_signal(page, thresholds["drawing_count"]):
        confirmed = llm_confirms_timing(text)
        return confirmed, ("llm_confirmed" if confirmed else "llm_rejected")

    return False, "none"


def page_needs_vision(page: fitz.Page, thresholds: dict[str, int]) -> bool:
    return classify_page(page, thresholds)[0]


def needs_vision(pdf_path: str) -> dict[int, bool]:
    doc = fitz.open(pdf_path)
    thresholds = compute_document_thresholds(doc)
    flags = {i + 1: page_needs_vision(page, thresholds) for i, page in enumerate(doc)}
    doc.close()
    return flags
