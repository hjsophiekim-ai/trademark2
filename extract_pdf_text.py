from pathlib import Path
from pypdf import PdfReader

pdf_files = [
    Path(r"docs\상표심사기준.pdf"),
    Path(r"docs\유사상품 심사기준(니스 제13판 기준).pdf"),
]

out_dir = Path(r"docs\parsed")
out_dir.mkdir(parents=True, exist_ok=True)

for pdf in pdf_files:
    reader = PdfReader(str(pdf))
    chunks = [f"# {pdf.stem}\n"]
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        chunks.append(f"\n\n--- page {i} ---\n\n{text}")
    out_path = out_dir / f"{pdf.stem}.md"
    out_path.write_text("".join(chunks), encoding="utf-8")
    print(f"Wrote: {out_path}")
