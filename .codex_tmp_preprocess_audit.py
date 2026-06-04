from pathlib import Path

from packages.core.document_reader import _excel_to_text

paths = [
    r"C:\Users\Raj Gandhi\Downloads\10011364-RFQ for Gasket.xlsx",
    r"C:\Users\Raj Gandhi\Downloads\SO 71409 BOM Gaskets R1.xlsx",
    r"C:\Users\Raj Gandhi\Downloads\Gasket -BOQ (1).xlsx",
    r"C:\Users\Raj Gandhi\Downloads\EXPORT PRICING - AXIOM RFQ-KA-25125.xlsx",
    r"C:\Users\Raj Gandhi\Downloads\GGPL - SPW (KA-25125) Customer spec.xlsx",
    r"C:\Users\Raj Gandhi\Downloads\Gasket -BOQ.xlsx",
]

for raw_path in paths:
    path = Path(raw_path)
    text, truncated, rows = _excel_to_text(path.read_bytes())
    lines = text.splitlines()
    print(f"\n### {path.name}")
    print(f"rows={rows} truncated={truncated} chars={len(text)} lines={len(lines)}")
    for line in lines[:6]:
        print(line)
    if len(lines) > 9:
        print("---tail---")
        for line in lines[-3:]:
            print(line)
