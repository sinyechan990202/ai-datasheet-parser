import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "parse_cache.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS page_parses (
    source_file TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    pipeline_version TEXT NOT NULL,
    tier0_text TEXT,
    tier0_shapes TEXT,
    tier1_tables TEXT,
    router_reason TEXT,
    used_vision INTEGER NOT NULL,
    vision_description TEXT,
    combined_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_file, page_number, pipeline_version)
)
"""

_ADDITIONAL_COLUMNS = {
    "tier1_tables": "TEXT",
    "tier0_shapes": "TEXT",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    # 스키마에 나중에 추가된 컬럼들은 이전에 만들어진 DB 파일에는 없을 수 있다.
    # CREATE TABLE IF NOT EXISTS는 기존 테이블을 건드리지 않으므로 직접 마이그레이션한다.
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(page_parses)")}
    for column, col_type in _ADDITIONAL_COLUMNS.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE page_parses ADD COLUMN {column} {col_type}")
    return conn


def get(source_file: str, page_number: int, pipeline_version: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT combined_text, used_vision FROM page_parses "
        "WHERE source_file = ? AND page_number = ? AND pipeline_version = ?",
        (source_file, page_number, pipeline_version),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    combined_text, used_vision = row
    return {
        "source": source_file,
        "page_number": page_number,
        "text": combined_text,
        "used_vision": bool(used_vision),
    }


def get_full(source_file: str, page_number: int, pipeline_version: str) -> dict | None:
    """Tier0/1/2 출력을 단계별로 그대로 보고 싶을 때 쓰는 조회 함수 (디버깅/품질 점검용)."""
    conn = _connect()
    row = conn.execute(
        "SELECT tier0_text, tier1_tables, router_reason, used_vision, vision_description, "
        "combined_text, created_at FROM page_parses "
        "WHERE source_file = ? AND page_number = ? AND pipeline_version = ?",
        (source_file, page_number, pipeline_version),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    tier0_text, tier1_tables, router_reason, used_vision, vision_description, combined_text, created_at = row
    return {
        "source_file": source_file,
        "page_number": page_number,
        "tier0_text": tier0_text,
        "tier1_tables": tier1_tables,
        "router_reason": router_reason,
        "used_vision": bool(used_vision),
        "vision_description": vision_description,
        "combined_text": combined_text,
        "created_at": created_at,
    }


def save(
    source_file: str,
    page_number: int,
    pipeline_version: str,
    tier0_text: str,
    tier1_tables: str,
    router_reason: str,
    used_vision: bool,
    vision_description: str | None,
    combined_text: str,
) -> None:
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO page_parses
           (source_file, page_number, pipeline_version, tier0_text, tier1_tables, router_reason,
            used_vision, vision_description, combined_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            source_file, page_number, pipeline_version, tier0_text, tier1_tables, router_reason,
            int(used_vision), vision_description, combined_text,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def delete_page(source_file: str, page_number: int) -> None:
    """특정 페이지의 모든 버전 캐시를 지운다 — 로직을 바꾸지 않고 그 페이지만 강제로 재파싱하고 싶을 때 사용."""
    conn = _connect()
    conn.execute("DELETE FROM page_parses WHERE source_file = ? AND page_number = ?", (source_file, page_number))
    conn.commit()
    conn.close()


def get_pages_missing_tier1(source_file: str, pipeline_version: str) -> list[dict]:
    """tier1_tables 컬럼이 생기기 전에 저장된 행들을 찾는다 (스키마 추가 이전 캐시 백필용)."""
    conn = _connect()
    rows = conn.execute(
        "SELECT page_number, tier0_text, vision_description FROM page_parses "
        "WHERE source_file = ? AND pipeline_version = ? AND tier1_tables IS NULL",
        (source_file, pipeline_version),
    ).fetchall()
    conn.close()
    return [{"page_number": r[0], "tier0_text": r[1], "vision_description": r[2]} for r in rows]


def update_tier1(source_file: str, page_number: int, pipeline_version: str, tier1_tables: str, combined_text: str) -> None:
    """기존 행의 tier0/vision 결과는 그대로 두고 tier1_tables와 combined_text만 갱신한다
    (Tier1은 로컬 연산이라 API 비용 없이 백필 가능)."""
    conn = _connect()
    conn.execute(
        "UPDATE page_parses SET tier1_tables = ?, combined_text = ? "
        "WHERE source_file = ? AND page_number = ? AND pipeline_version = ?",
        (tier1_tables, combined_text, source_file, page_number, pipeline_version),
    )
    conn.commit()
    conn.close()


def get_pages_missing_tier0_shapes(source_file: str, pipeline_version: str) -> list[int]:
    """tier0_shapes 컬럼이 생기기 전에 저장된 행들의 페이지 번호를 찾는다."""
    conn = _connect()
    rows = conn.execute(
        "SELECT page_number FROM page_parses "
        "WHERE source_file = ? AND pipeline_version = ? AND tier0_shapes IS NULL",
        (source_file, pipeline_version),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def update_tier0_shapes(source_file: str, page_number: int, pipeline_version: str, tier0_shapes: str) -> None:
    """tier0_shapes만 갱신한다. combined_text/tier1/vision은 건드리지 않는다 — 원시 도형 덤프는
    아직 검색·요약 파이프라인에 섞지 않고 별도 컬럼에서 확인만 하기 위한 실험적 데이터이기 때문."""
    conn = _connect()
    conn.execute(
        "UPDATE page_parses SET tier0_shapes = ? "
        "WHERE source_file = ? AND page_number = ? AND pipeline_version = ?",
        (tier0_shapes, source_file, page_number, pipeline_version),
    )
    conn.commit()
    conn.close()
