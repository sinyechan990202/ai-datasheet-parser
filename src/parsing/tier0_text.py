import pymupdf as fitz

# ASCII 파형 재구성 튜닝 파라미터. 특정 문서에 맞춘 값이 아니라 "일반적인 클럭/타이밍
# 다이어그램의 선 굵기·펄스 폭" 정도를 가정한 값이라 완벽히 맞아떨어지지 않을 수 있다.
_RAIL_Y_TOLERANCE = 3.0  # 이 이내로 붙어있는 수평선은 같은 "레일"로 묶는다
_MIN_RAIL_SPAN = 10.0  # 레일의 전체 수평 커버리지가 이보다 작으면 화살표/눈금 같은 잡음으로 보고 버린다
_MAX_TRACE_PAIR_GAP = 40.0  # 두 레일이 이 거리 안에 있으면 하나의 신호(high/low)로 묶는다
_MAX_LINE_WIDTH = 200  # 한 줄 최대 문자 수
_MIN_CHAR_STEP = 2.0  # 문자 하나당 최소 pt 폭


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


def extract_ascii_waveforms(pdf_path: str) -> dict[int, str]:
    """벡터 드로잉의 선분을 y좌표로 묶어 "레일"을 찾고, 인접한 두 레일을 하나의 신호로 묶어
    ASCII(-, _, |)로 재구성한다. 클럭/타이밍 파형처럼 두 레벨을 오가는 도형은 꽤 깨끗하게
    나오지만, 화살표/치수선/범례처럼 파형이 아닌 도형은 지저분한 조각으로 나올 수 있다 —
    도형 종류를 구분하지 않고 좌표만 보고 훑는 근사치이기 때문이다."""
    doc = fitz.open(pdf_path)
    result = {}
    for i, page in enumerate(doc):
        result[i + 1] = _render_page_waveform(page)
    doc.close()
    return result


def _render_page_waveform(page) -> str:
    h_segs: list[tuple[float, float, float]] = []  # (y, x1, x2)
    v_segs: list[tuple[float, float, float]] = []  # (x, y1, y2)

    for drawing in page.get_drawings():
        for item in drawing["items"]:
            kind = item[0]
            if kind == "l":
                p1, p2 = item[1], item[2]
                x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
                if abs(y2 - y1) <= _RAIL_Y_TOLERANCE and abs(x2 - x1) > _RAIL_Y_TOLERANCE:
                    h_segs.append((round((y1 + y2) / 2, 1), min(x1, x2), max(x1, x2)))
                elif abs(x2 - x1) <= _RAIL_Y_TOLERANCE and abs(y2 - y1) > _RAIL_Y_TOLERANCE:
                    v_segs.append((round((x1 + x2) / 2, 1), min(y1, y2), max(y1, y2)))
            elif kind == "re":
                r = item[1]
                h_segs.append((round(r.y0, 1), r.x0, r.x1))
                h_segs.append((round(r.y1, 1), r.x0, r.x1))
                v_segs.append((round(r.x0, 1), r.y0, r.y1))
                v_segs.append((round(r.x1, 1), r.y0, r.y1))

    if not h_segs:
        return ""

    h_segs.sort(key=lambda s: s[0])
    rails = []
    for y, x1, x2 in h_segs:
        if rails and y - rails[-1]["y"] <= _RAIL_Y_TOLERANCE:
            rails[-1]["segs"].append((x1, x2))
        else:
            rails.append({"y": y, "segs": [(x1, x2)]})

    rails = [r for r in rails if sum(x2 - x1 for x1, x2 in r["segs"]) >= _MIN_RAIL_SPAN]
    if not rails:
        return ""

    all_x = [x for r in rails for pair in r["segs"] for x in pair]
    x_min, x_max = min(all_x), max(all_x)
    width = max(20, min(_MAX_LINE_WIDTH, int((x_max - x_min) / _MIN_CHAR_STEP) + 1))
    step = (x_max - x_min) / width if width else 1.0

    def col(x: float) -> int:
        if step == 0:
            return 0
        return max(0, min(width - 1, int((x - x_min) / step)))

    traces: list[tuple] = []
    used = [False] * len(rails)
    for idx in range(len(rails) - 1):
        if used[idx]:
            continue
        if rails[idx + 1]["y"] - rails[idx]["y"] <= _MAX_TRACE_PAIR_GAP:
            traces.append((rails[idx], rails[idx + 1]))
            used[idx] = used[idx + 1] = True
    for idx, rail in enumerate(rails):
        if not used[idx]:
            traces.append((rail,))

    lines = []
    for trace in traces:
        line = [" "] * width
        if len(trace) == 2:
            top, bottom = sorted(trace, key=lambda r: r["y"])
            for x1, x2 in top["segs"]:
                for c in range(col(x1), col(x2) + 1):
                    line[c] = "-"
            for x1, x2 in bottom["segs"]:
                for c in range(col(x1), col(x2) + 1):
                    line[c] = "_"
            for x, y1, y2 in v_segs:
                if y1 - _RAIL_Y_TOLERANCE <= top["y"] and y2 + _RAIL_Y_TOLERANCE >= bottom["y"]:
                    line[col(x)] = "|"
        else:
            for x1, x2 in trace[0]["segs"]:
                for c in range(col(x1), col(x2) + 1):
                    line[c] = "-"
        rendered = "".join(line).rstrip()
        if rendered.strip():
            lines.append(rendered)

    return "\n".join(lines)
