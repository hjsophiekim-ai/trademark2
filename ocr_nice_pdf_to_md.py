from pathlib import Path
import fitz
import pytesseract

pdf_path = Path(r"docs\지식재산처_상품분류_니스분류.pdf")
out_dir = Path(r"docs\parsed")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "지식재산처_상품분류_니스분류.md"

# Tesseract 설치 경로
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

doc = fitz.open(pdf_path)
chunks = [f"# {pdf_path.stem}\n"]

for i, page in enumerate(doc, start=1):
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_path = out_dir / f"page_{i}.png"
    pix.save(img_path)

    text = pytesseract.image_to_string(str(img_path), lang="kor+eng")
    chunks.append(f"\n\n--- page {i} ---\n\n{text.strip()}\n")

out_path.write_text("".join(chunks), encoding="utf-8")
print(f"Wrote: {out_path}")
