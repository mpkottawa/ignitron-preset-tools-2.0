#!/usr/bin/env python3
"""Generate Ignitron PresetList.pdf from an Ignitron data folder."""

import os
import platform
import subprocess
import sys
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:
    colors = letter = getSampleStyleSheet = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None


def default_data_dir():
    candidates = [
        Path(r"T:\ignitron\data"),
        Path.cwd() / "data",
        Path(__file__).resolve().parent.parent / "data",
        Path(os.path.sep) / "ignitron" / "data",
    ]
    for candidate in candidates:
        if (candidate / "PresetList.txt").exists():
            return candidate
    return candidates[0]


def generate_chart(base_dir=None, open_pdf=True):
    base_dir = Path(base_dir) if base_dir else default_data_dir()
    txt_file = base_dir / "PresetList.txt"
    output_path = base_dir / "PresetList.pdf"

    if not txt_file.exists():
        print(f"PresetList.txt not found at {txt_file}")
        return None

    banks = []
    current_bank = None
    for raw_line in txt_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-- Bank"):
            current_bank = [line.replace("--", "").strip(), []]
            banks.append(current_bank)
            continue
        if current_bank is None:
            current_bank = ["Bank 1", []]
            banks.append(current_bank)
        current_bank[1].append(Path(line).stem.replace("_", " "))

    table_data = [["Bank", "Slot 1", "Slot 2", "Slot 3", "Slot 4"]]
    for bank, presets in banks:
        row = list(presets[:4])
        while len(row) < 4:
            row.append("-")
        table_data.append([bank] + row)

    if SimpleDocTemplate is None:
        write_simple_pdf(output_path, table_data)
        print(f"Preset chart generated: {output_path}")
        return output_path

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=24, leftMargin=24)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("<font color='#f5a623'><b>Ignitron Preset Chart</b></font>", styles["Title"]),
        Spacer(1, 12),
    ]

    table = Table(table_data, colWidths=[64, 112, 112, 112, 112], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f5a623")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f7f1e5"), colors.HexColor("#ead7b7")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#6d5d42")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    doc.build(elements)

    print(f"Preset chart generated: {output_path}")

    if open_pdf:
        try:
            if platform.system() == "Windows":
                os.startfile(output_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", output_path])
            else:
                subprocess.Popen(["xdg-open", output_path])
        except Exception:
            pass

    return output_path


def write_simple_pdf(output_path, rows):
    def pdf_escape(value):
        return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = ["BT", "/F1 18 Tf", "50 750 Td", "(Ignitron Preset Chart) Tj", "/F1 8 Tf", "0 -24 Td"]
    for row in rows:
        text = "   |   ".join(row)
        lines.append(f"({pdf_escape(text)}) Tj")
        lines.append("0 -14 Td")
    lines.append("ET")
    stream = "\n".join(lines).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    output_path.write_bytes(content)


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else None
    generate_chart(folder)
