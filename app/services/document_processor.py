"""
Document processor for educational, legal, academic, and general-purpose documents.
Handles PDF and plain text files.

Chunking strategy:
  1. Structural section splitting — splits at detected headings/section markers.
  2. Fixed-size fallback — used when no recognisable structure is detected.

Supported domains (non-exhaustive):
  - Legal / regulatory   : Article, Section, Rule, Clause, Provision, Statute
  - Educational          : Chapter, Lesson, Unit, Module, Topic
  - Academic             : Part, Appendix, Exhibit
  - Numbered headings    : "1.1 Introduction", "2. Methods"
"""
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Section patterns — ordered most-specific → most-general.
# Each pattern anchors to the start of a line (enforced by the MULTILINE flag
# on COMBINED_PATTERN below).
# ---------------------------------------------------------------------------
SECTION_PATTERNS = [
    # Legal / regulatory
    r"(?:ARTICLE|Article|Art\.?)\s+(?:[IVXLCDM]+|\d+)",        # Article XV / Art. 315
    r"(?:SECTION|Section|Sec\.?)\s+\d+(?:\.\d+)*",             # Section 1 / Sec. 3.2
    r"(?:Rule|RULE)\s+(?:[IVXLCDM]+|\d+)",                      # Rule IV
    r"(?:CLAUSE|Clause)\s+\d+(?:\.\d+)*",                       # Clause 5 / Clause 5.1.2
    r"(?:PROVISION|Provision)\s+\d+",                           # Provision 3
    r"(?:STATUTE|Statute)\s+\d+",                               # Statute 42
    r"(?:PARAGRAPH|Para(?:graph)?\.?)\s+\d+(?:\.\d+)*",         # Paragraph 4 / Para. 4.1
    r"(?:SUB-?SECTION|Sub-?section)\s+\d+(?:\.\d+)*",           # Subsection 2.1

    # Educational / curriculum
    r"(?:LESSON|Lesson)\s+\d+",                                  # Lesson 1
    r"(?:UNIT|Unit)\s+(?:[IVXLCDM]+|\d+)",                      # Unit 3 / Unit III
    r"(?:MODULE|Module)\s+(?:[IVXLCDM]+|\d+)",                  # Module 2
    r"(?:TOPIC|Topic)\s+\d+",                                    # Topic 5

    # Structural / academic
    r"(?:CHAPTER|Chapter)\s+(?:[IVXLCDM]+|\d+)",                # Chapter III / Chapter 7
    r"(?:TITLE|Title)\s+(?:[IVXLCDM]+|\d+)",                    # Title II
    r"(?:PART|Part)\s+(?:[IVXLCDM]+|\d+)",                      # Part I / Part 3
    r"(?:APPENDIX|Appendix)\s+(?:[A-Z]|\d+)",                   # Appendix A / Appendix 1
    r"(?:EXHIBIT|Exhibit)\s+(?:[A-Z]|\d+)",                     # Exhibit B

    # Numbered outline headings  (e.g. "1.1 Introduction", "2. Overview")
    # Only matches when the number is at the very start of the line.
    r"\d+(?:\.\d+)+\s+[A-Z]",                                   # 1.1 Heading
    r"\d+\.\s{1,4}[A-Z]",                                       # 1. Heading
]

COMBINED_PATTERN = re.compile(
    r"(?m)^(?:" + "|".join(SECTION_PATTERNS) + r")\b",
    re.IGNORECASE,
)

# Fixed-size chunking fallback constants
CHUNK_SIZE = 800        # characters per chunk
CHUNK_OVERLAP = 150     # overlap between consecutive chunks


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber is required for PDF extraction. Run: pip install pdfplumber"
        )

    parts: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)

    return "\n".join(parts)


def extract_text_from_txt(file_path: str) -> str:
    """Read a plain-text file, replacing un-decodable bytes."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_text(file_path: str) -> str:
    """
    Extract text from a file based on its extension.
    Supports: .pdf, .txt, .text, .md
    """
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    if suffix in {".txt", ".text", ".md"}:
        return extract_text_from_txt(file_path)
    raise ValueError(f"Unsupported file type: {suffix!r}. Supported: .pdf, .txt")


# ---------------------------------------------------------------------------
# Chunking strategies
# ---------------------------------------------------------------------------

def chunk_by_sections(text: str) -> list[dict]:
    """
    Split text at structural section boundaries.

    Returns:
        List of ``{"section_label": str, "text": str}`` dicts.
        Returns an empty list if no section markers are detected.
    """
    matches = list(COMBINED_PATTERN.finditer(text))
    if not matches:
        return []

    chunks: list[dict] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk_text = text[start:end].strip()

        if len(chunk_text) < 20:
            continue  # Skip near-empty headings

        section_label = chunk_text.split("\n")[0].strip()[:100]
        chunks.append({"section_label": section_label, "text": chunk_text})

    return chunks


def chunk_by_fixed_size(text: str) -> list[dict]:
    """
    Fixed-size character chunking with overlap.
    Fallback when no section markers are detected.

    Returns:
        List of ``{"section_label": str, "text": str}`` dicts.
    """
    chunks: list[dict] = []
    start = 0
    chunk_number = 1

    while start < len(text):
        chunk_text = text[start : start + CHUNK_SIZE].strip()
        if len(chunk_text) < 20:
            break
        chunks.append({"section_label": f"Chunk {chunk_number}", "text": chunk_text})
        start += CHUNK_SIZE - CHUNK_OVERLAP
        chunk_number += 1

    return chunks


# ---------------------------------------------------------------------------
# Public pipeline
# ---------------------------------------------------------------------------

def process_document(file_path: str, title: str, year: int) -> dict:
    """
    Full pipeline: extract text → detect and apply chunking strategy.

    Returns:
        {
            "title":       str,
            "year":        int,
            "total_chars": int,
            "chunk_count": int,
            "strategy":    "sections" | "fixed_size",
            "chunks":      [{"section_label": str, "text": str}, ...],
        }

    Raises:
        ValueError: If no text could be extracted or no chunks produced.
    """
    text = extract_text(file_path)
    if not text.strip():
        raise ValueError("No text could be extracted from the document.")

    chunks = chunk_by_sections(text)
    strategy = "sections"

    if not chunks:
        chunks = chunk_by_fixed_size(text)
        strategy = "fixed_size"

    if not chunks:
        raise ValueError("Could not chunk the document. It may be empty or unreadable.")

    return {
        "title": title,
        "year": year,
        "total_chars": len(text),
        "chunk_count": len(chunks),
        "strategy": strategy,
        "chunks": chunks,
    }
