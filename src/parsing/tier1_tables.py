import pdfplumber


def extract_tables_per_page(pdf_path: str) -> dict[int, list[list[list[str]]]]:
    tables_by_page = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                tables_by_page[i + 1] = tables
    return tables_by_page


def table_to_markdown(table: list[list[str]]) -> str:
    rows = [row for row in table if row]
    if not rows:
        return ""
    lines = ["| " + " | ".join((cell or "").replace("\n", " ") for cell in row) + " |" for row in rows]
    header_sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
    lines.insert(1, header_sep)
    return "\n".join(lines)
