#!/usr/bin/env python3
"""
md_to_docx.py — convert an SRS markdown file to .docx with the IndiaMART cover page.

Pipeline:
    1. Pandoc-convert <input.md> to a temp body.docx.
    2. Clone assets/srs-template.docx, replace `{{ API_NAME }}` with the uppercased
       --api-name input inside word/document.xml (preserving leading whitespace).
    3. Open the modified template with python-docx, append every paragraph and
       table from the pandoc body in order. The cover (a grouped drawing) lives
       in the template's first paragraph and is left untouched.
    4. Insert an explicit page break ahead of the appended body so SRS content
       starts on page 2 regardless of how the renderer flows the anchored cover.
    5. Save to <output.docx>.

Usage:
    python3 md_to_docx.py <input.md> <output.docx> --api-name "Master Detail API"

Exit codes:
    0  success
    1  bad arguments / input missing or empty
    2  pandoc not installed
    3  python-docx not installed
    4  pandoc conversion failed
    5  template missing or malformed
    6  python-docx body merge failed
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

PLACEHOLDER = "{{ API_NAME }}"
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "srs-srs-template.docx"


def die(code: int, msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", type=Path, help="SRS markdown file")
    p.add_argument("output", type=Path, help="destination .docx file")
    p.add_argument("--api-name", required=True, help="API name to render on the cover page")
    return p.parse_args()


def check_dependencies() -> int:
    if shutil.which("pandoc") is None:
        return die(2, "pandoc is not installed in this sandbox; rebuild company-claude-v1 with pandoc in the Dockerfile.")
    try:
        import docx  # noqa: F401
    except ImportError:
        return die(3, "python-docx is not installed in this sandbox; rebuild company-claude-v1 with `pip install python-docx`.")
    return 0


def validate_input(path: Path) -> int:
    if not path.is_file():
        return die(1, f"input file not found: {path}")
    if path.stat().st_size == 0:
        return die(1, f"input file is empty: {path}")
    if not path.read_text(encoding="utf-8", errors="ignore").strip():
        return die(1, f"input file has no content (whitespace only): {path}")
    return 0


def validate_template() -> int:
    if not TEMPLATE.is_file():
        return die(5, f"cover template missing: {TEMPLATE}")
    try:
        with zipfile.ZipFile(TEMPLATE) as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError) as e:
        return die(5, f"srs-template.docx is not a valid docx archive: {e}")
    if PLACEHOLDER not in doc_xml:
        return die(5, f"srs-template.docx does not contain the placeholder {PLACEHOLDER!r}")
    return 0


def pandoc_convert(src: Path, dst: Path) -> int:
    """Convert markdown to docx via pandoc; no cover, just the body."""
    cmd = [
        "pandoc",
        str(src),
        "-o", str(dst),
        "--from=gfm+pipe_tables",
        "--to=docx",
        "-V", "papersize=letter",
        "-V", "geometry:margin=1in",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = f"pandoc failed (exit {result.returncode})"
        if result.stderr.strip():
            msg += f": {result.stderr.strip()}"
        return die(4, msg)
    if not dst.is_file() or dst.stat().st_size == 0:
        return die(4, f"pandoc produced no output at {dst}")
    return 0


def write_cover(template_src: Path, template_dst: Path, api_name: str) -> int:
    """Copy srs-template.docx to template_dst, replacing the placeholder in document.xml."""
    replacement = api_name.upper()
    try:
        with zipfile.ZipFile(template_src, "r") as zin, zipfile.ZipFile(template_dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    text = data.decode("utf-8")
                    text = text.replace(PLACEHOLDER, replacement)
                    data = text.encode("utf-8")
                zout.writestr(item, data)
    except (zipfile.BadZipFile, OSError) as e:
        return die(5, f"failed to write cover docx: {e}")
    return 0


def merge_body_into_cover(cover_path: Path, body_path: Path, output_path: Path) -> int:
    """Append every paragraph + table from body_path into cover_path (after a page break)."""
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        return die(3, "python-docx import failed (this should have been caught earlier).")

    try:
        cover = Document(str(cover_path))
        body = Document(str(body_path))
    except Exception as e:
        return die(6, f"failed to open docx for merge: {e}")

    try:
        cover_body_el = cover.element.body
        # The template's sectPr lives at the end of body; new content must be
        # inserted before it so the section properties stay last.
        sect_pr = cover_body_el.find(qn("w:sectPr"))

        # Insert an explicit page break so SRS content starts on a fresh page,
        # regardless of how the anchored cover drawing flows.
        page_break_p = OxmlElement("w:p")
        page_break_r = OxmlElement("w:r")
        page_break = OxmlElement("w:br")
        page_break.set(qn("w:type"), "page")
        page_break_r.append(page_break)
        page_break_p.append(page_break_r)
        if sect_pr is not None:
            sect_pr.addprevious(page_break_p)
        else:
            cover_body_el.append(page_break_p)

        # Copy every top-level <w:p> and <w:tbl> from the body docx, preserving order.
        body_root = body.element.body
        for child in list(body_root):
            tag = child.tag
            if tag == qn("w:p") or tag == qn("w:tbl"):
                copied = deepcopy(child)
                if sect_pr is not None:
                    sect_pr.addprevious(copied)
                else:
                    cover_body_el.append(copied)
            # Skip body's own sectPr — we keep the cover's.

        cover.save(str(output_path))
    except Exception as e:
        return die(6, f"failed to merge body into cover: {e}")

    if not output_path.is_file() or output_path.stat().st_size == 0:
        return die(6, f"merge produced no output at {output_path}")
    return 0


def main() -> int:
    args = parse_args()

    rc = check_dependencies()
    if rc:
        return rc

    rc = validate_input(args.input)
    if rc:
        return rc

    rc = validate_template()
    if rc:
        return rc

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        body_docx = tmp_dir / "body.docx"
        cover_docx = tmp_dir / "cover.docx"

        rc = pandoc_convert(args.input, body_docx)
        if rc:
            return rc

        rc = write_cover(TEMPLATE, cover_docx, args.api_name)
        if rc:
            return rc

        rc = merge_body_into_cover(cover_docx, body_docx, args.output)
        if rc:
            return rc

    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
