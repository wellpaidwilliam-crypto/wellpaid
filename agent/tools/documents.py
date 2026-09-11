"""WellPaiD Trader - File analysis tools (V0.5, Option A).

Sandboxed, read-only access to local user data:

- FilesTool: list/stat/read/hash files confined under a root directory.
  Refuses absolute paths, `..` escapes, and sensitive filenames
  (.env, keys, tokens, credentials).
- SheetsTool: read .xlsx workbooks with the standard library only
  (xlsx is a ZIP of XML: zipfile + xml.etree). Sheet list, row
  preview, and numeric column stats. No formulas are evaluated.
- PdfTool: PDF text/metadata when an optional backend (pypdf or
  pdfplumber) is installed; otherwise fails gracefully with an install
  hint. Stdlib-only policy means no PDF backend is required.
- DxfTool: read-only AutoCAD DXF inventory (entity counts by type,
  layers, extents) with pure-stdlib group-code parsing. Capped sizes.
"""

import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Any, Optional
import xml.etree.ElementTree as ET

try:
    from agent.tools.base import SafetyClass, Tool, ToolResult
except ImportError:
    from .base import SafetyClass, Tool, ToolResult

MAX_READ_BYTES = 100 * 1024  # 100 KiB per file read
MAX_LIST_ENTRIES = 500
MAX_XLSX_BYTES = 20 * 1024 * 1024
MAX_XLSX_ROWS = 10_000
MAX_DXF_BYTES = 50 * 1024 * 1024

SENSITIVE_NAMES = (
    ".env",
    ".pem",
    ".key",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "secret",
    "token",
    "password",
)


def _confine(root: Path, rel: str) -> Optional[Path]:
    """Resolve `rel` inside `root`. None on escape/absolute/sensitive."""
    if not rel or rel.strip() == "":
        return None
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    lowered = candidate.name.lower()
    if any(marker in lowered for marker in SENSITIVE_NAMES):
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


class FilesTool(Tool):
    """Sandboxed file inspection under one root directory."""

    name = "files"
    description = (
        "List/stat/read/hash files under the tool root "
        "('list' dir, 'read' path, 'stat' path, 'hash' path). "
        "Absolute paths, escapes and sensitive files are refused."
    )
    safety = SafetyClass.LOCAL_READ
    schema = {
        "action": {
            "type": "string",
            "required": True,
            "description": "list|read|stat|hash",
        },
        "path": {
            "type": "string",
            "required": False,
            "description": "Relative path (default '.' for list).",
        },
    }

    def __init__(self, root: Any = None) -> None:
        """Confine browsing to `root` (default: current directory)."""
        self.root = Path(root) if root is not None else Path.cwd()

    def execute(self, args: dict) -> ToolResult:
        action = args["action"]
        rel = args.get("path", ".") or "."
        if action == "list":
            target = self.root if rel == "." else _confine(self.root, rel)
            if target is None or not target.is_dir():
                return ToolResult(False, "directory not accessible")
            entries = sorted(target.iterdir())[:MAX_LIST_ENTRIES]
            return ToolResult(
                True,
                f"{len(entries)} entr(ies) in {rel}",
                data={
                    "entries": [
                        {
                            "name": e.name,
                            "dir": e.is_dir(),
                            "size": e.stat().st_size if e.is_file() else 0,
                        }
                        for e in entries
                    ]
                },
            )
        target = _confine(self.root, rel)
        if target is None or not target.is_file():
            return ToolResult(False, "file not accessible")
        if action == "stat":
            stat = target.stat()
            return ToolResult(
                True,
                f"{rel}: {stat.st_size} bytes",
                data={"path": rel, "size": stat.st_size},
            )
        if action == "hash":
            digest = hashlib.sha256()
            with open(target, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    digest.update(chunk)
            return ToolResult(
                True,
                f"{rel}: sha256 {digest.hexdigest()[:16]}...",
                data={"path": rel, "sha256": digest.hexdigest()},
            )
        if action == "read":
            if target.stat().st_size > MAX_READ_BYTES:
                return ToolResult(
                    False,
                    f"file too large (>{MAX_READ_BYTES} bytes); use hash/stat",
                )
            try:
                text = target.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                return ToolResult(
                    False, "not a readable text file; use hash/stat"
                )
            return ToolResult(
                True, f"{rel}: {len(text)} chars", data={"path": rel, "text": text}
            )
        return ToolResult(False, f"unknown action: {action}")


# -- xlsx via stdlib ---------------------------------------------------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _xlsx_sheet_names(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Return [(name, rel_path)] for each worksheet."""
    try:
        raw = zf.read("xl/workbook.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    out = []
    rid_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    for sheet in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
        out.append(
            (sheet.get("name", "?"), sheet.get(f"{{{rid_ns}}}id", ""))
        )
    try:
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return [(name, "") for name, _ in out]
    targets = {}
    for rel in rels.iter():
        if rel.get("Id"):
            targets[rel.get("Id")] = rel.get("Target", "")
    resolved = []
    for name, rid in out:
        target = targets.get(rid, "")
        target = target.replace("../", "xl/")
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        resolved.append((name, target))
    return resolved


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        raw = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings = []
    for elem in ET.fromstring(raw).iter(f"{{{_NS['m']}}}t"):
        strings.append(elem.text or "")
    return strings


def _xlsx_rows(zf: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[Any]]:
    """Parse a worksheet into rows (shared strings resolved, else raw)."""
    rows: list[list[Any]] = []
    try:
        raw = zf.read(path)
    except KeyError:
        return rows
    for row in ET.fromstring(raw).iter(f"{{{_NS['m']}}}row"):
        cells: list[Any] = []
        for cell in row.iter(f"{{{_NS['m']}}}c"):
            cell_type = cell.get("t", "n")
            value_elem = cell.find(f"{{{_NS['m']}}}v")
            inline = cell.find(f"{{{_NS['m']}}}is/{{{_NS['m']}}}t")
            if inline is not None:
                cells.append(inline.text or "")
            elif value_elem is None or value_elem.text is None:
                cells.append("")
            elif cell_type == "s":
                try:
                    cells.append(shared[int(value_elem.text)])
                except (IndexError, ValueError):
                    cells.append("")
            else:
                try:
                    text = value_elem.text
                    cells.append(
                        float(text) if "." in text or "e" in text.lower() else int(text)
                    )
                except ValueError:
                    cells.append(value_elem.text)
        rows.append(cells)
        if len(rows) >= MAX_XLSX_ROWS:
            break
    return rows


class SheetsTool(Tool):
    """Read-only .xlsx inspection with the standard library.

    Lists sheets, previews rows, and computes numeric column stats.
    Formulas are reported as cached values or blanks — never evaluated.
    """

    name = "sheets"
    description = (
        "Inspect .xlsx workbooks ('sheets' names, 'preview' rows, "
        "'stats' numeric columns). Stdlib only; formulas not evaluated."
    )
    safety = SafetyClass.LOCAL_READ
    schema = {
        "action": {
            "type": "string",
            "required": True,
            "description": "sheets|preview|stats",
        },
        "path": {
            "type": "string",
            "required": True,
            "description": "Relative workbook path under the tool root.",
        },
        "sheet": {
            "type": "string",
            "required": False,
            "description": "Sheet name (default first sheet).",
        },
        "rows": {
            "type": "integer",
            "required": False,
            "description": "Preview rows (default 20, max 100).",
        },
    }

    def __init__(self, root: Any = None) -> None:
        """Confine workbooks to `root` (default: current directory)."""
        self.root = Path(root) if root is not None else Path.cwd()

    def _open(self, rel: str):
        target = _confine(self.root, rel)
        if target is None or not target.is_file():
            return None, ToolResult(False, "workbook not accessible")
        if target.suffix.lower() not in (".xlsx", ".xlsm"):
            return None, ToolResult(False, "only .xlsx/.xlsm workbooks")
        if target.stat().st_size > MAX_XLSX_BYTES:
            return None, ToolResult(False, "workbook too large (>20 MiB)")
        try:
            zf = zipfile.ZipFile(target)
            if "xl/workbook.xml" not in zf.namelist():
                return None, ToolResult(False, "not a valid workbook")
        except zipfile.BadZipFile:
            return None, ToolResult(False, "not a valid workbook")
        return zf, None

    def _pick(self, zf: zipfile.ZipFile, wanted: Optional[str]):
        names = _xlsx_sheet_names(zf)
        if not names:
            return None, ToolResult(False, "no worksheets found")
        if wanted:
            for name, path in names:
                if name == wanted:
                    return (name, path), None
            return None, ToolResult(False, f"sheet not found: {wanted}")
        return names[0], None

    def execute(self, args: dict) -> ToolResult:
        action = args["action"]
        zf, error = self._open(args["path"])
        if error is not None:
            return error
        try:
            if action == "sheets":
                names = [name for name, _ in _xlsx_sheet_names(zf)]
                return ToolResult(
                    True,
                    f"{len(names)} sheet(s)",
                    data={"sheets": names},
                )
            picked, error = self._pick(zf, args.get("sheet"))
            if error is not None:
                return error
            name, path = picked
            rows = _xlsx_rows(zf, path, _xlsx_shared_strings(zf))
            if action == "preview":
                limit = args.get("rows", 20)
                if isinstance(limit, bool) or not isinstance(limit, int):
                    return ToolResult(False, "rows must be an integer")
                limit = max(1, min(100, limit))
                return ToolResult(
                    True,
                    f"{name}: {len(rows)} row(s)",
                    data={"sheet": name, "rows_total": len(rows), "preview": rows[:limit]},
                )
            if action == "stats":
                stats = []
                width = max((len(r) for r in rows), default=0)
                for col in range(width):
                    values = [
                        r[col] for r in rows if col < len(r) and isinstance(r[col], (int, float)) and not isinstance(r[col], bool)
                    ]
                    if values:
                        stats.append(
                            {
                                "column": col,
                                "count": len(values),
                                "min": min(values),
                                "max": max(values),
                                "mean": sum(values) / len(values),
                            }
                        )
                return ToolResult(
                    True,
                    f"{name}: {len(stats)} numeric column(s)",
                    data={"sheet": name, "rows_total": len(rows), "columns": stats},
                )
        finally:
            zf.close()
        return ToolResult(False, f"unknown action: {action}")


class PdfTool(Tool):
    """PDF text/metadata via optional backends (graceful without them)."""

    name = "pdf"
    description = (
        "Extract PDF text/metadata ('info'|'text'). Requires optional "
        "pypdf or pdfplumber; fails with an install hint otherwise."
    )
    safety = SafetyClass.LOCAL_READ
    schema = {
        "action": {"type": "string", "required": True, "description": "info|text"},
        "path": {
            "type": "string",
            "required": True,
            "description": "Relative PDF path under the tool root.",
        },
        "pages": {
            "type": "string",
            "required": False,
            "description": "Page range e.g. '1-3' (default all, capped at 50).",
        },
    }

    HINT = (
        "no PDF backend installed. Install one for PDF support: "
        "pip install pypdf  (or pdfplumber). "
        "Stdlib-only policy: PDF support stays optional."
    )

    def __init__(self, root: Any = None) -> None:
        """Confine PDFs to `root` (default: current directory)."""
        self.root = Path(root) if root is not None else Path.cwd()

    def _backend(self):
        try:
            from pypdf import PdfReader

            return ("pypdf", PdfReader)
        except ImportError:
            pass
        try:
            import pdfplumber

            return ("pdfplumber", pdfplumber)
        except ImportError:
            pass
        return (None, None)

    def execute(self, args: dict) -> ToolResult:
        target = _confine(self.root, args["path"])
        if target is None or not target.is_file():
            return ToolResult(False, "file not accessible")
        if target.suffix.lower() != ".pdf":
            return ToolResult(False, "only .pdf files")
        kind, backend = self._backend()
        if backend is None:
            return ToolResult(False, self.HINT)
        action = args["action"]
        try:
            if kind == "pypdf":
                reader = backend(str(target))
                pages = len(reader.pages)
                if action == "info":
                    meta = dict(reader.metadata or {})
                    return ToolResult(
                        True,
                        f"{pages} page(s)",
                        data={"pages": pages, "metadata": meta, "backend": kind},
                    )
                if action == "text":
                    wanted = self._pages(args.get("pages"), pages)
                    texts = [
                        reader.pages[i].extract_text() or "" for i in wanted
                    ]
                    return ToolResult(
                        True,
                        f"{len(texts)} page(s) extracted",
                        data={"pages": pages, "texts": texts, "backend": kind},
                    )
            else:  # pdfplumber
                import pdfplumber as _pl  # noqa: F401 (backend probe above)

                with backend.open(str(target)) as doc:
                    pages = len(doc.pages)
                    if action == "info":
                        return ToolResult(
                            True,
                            f"{pages} page(s)",
                            data={"pages": pages, "metadata": dict(doc.metadata or {}), "backend": kind},
                        )
                    if action == "text":
                        wanted = self._pages(args.get("pages"), pages)
                        texts = [doc.pages[i].extract_text() or "" for i in wanted]
                        return ToolResult(
                            True,
                            f"{len(texts)} page(s) extracted",
                            data={"pages": pages, "texts": texts, "backend": kind},
                        )
        except Exception as exc:  # noqa: BLE001 - corrupt PDFs fail softly
            return ToolResult(False, f"cannot read PDF: {type(exc).__name__}")
        return ToolResult(False, f"unknown action: {action}")

    @staticmethod
    def _pages(spec: Optional[str], total: int) -> list[int]:
        if not spec:
            return list(range(min(total, 50)))
        match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", spec)
        if not match:
            return list(range(min(total, 50)))
        start = max(1, int(match.group(1)))
        end = min(total, int(match.group(2) or start), start + 49)
        return list(range(start - 1, end))


class DxfTool(Tool):
    """Read-only AutoCAD DXF inventory with pure-stdlib parsing.

    Counts entities by type, lists layers, and reports HEADER extents.
    Never modifies the file; files over the cap are refused, not sampled
    (a sample would silently misreport the drawing).
    """

    name = "dxf"
    description = (
        "Inventory a .dxf drawing: entity counts by type, layers, "
        "extents ('inventory'). Read-only, stdlib only."
    )
    safety = SafetyClass.LOCAL_READ
    schema = {
        "action": {"type": "string", "required": True, "description": "inventory"},
        "path": {
            "type": "string",
            "required": True,
            "description": "Relative .dxf path under the tool root.",
        },
    }

    def __init__(self, root: Any = None) -> None:
        """Confine drawings to `root` (default: current directory)."""
        self.root = Path(root) if root is not None else Path.cwd()

    def execute(self, args: dict) -> ToolResult:
        if args["action"] != "inventory":
            return ToolResult(False, f"unknown action: {args['action']}")
        target = _confine(self.root, args["path"])
        if target is None or not target.is_file():
            return ToolResult(False, "file not accessible")
        if target.suffix.lower() != ".dxf":
            return ToolResult(False, "only .dxf files")
        if target.stat().st_size > MAX_DXF_BYTES:
            return ToolResult(False, "drawing too large (>50 MiB)")
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                pairs = [
                    (code.strip(), value.rstrip("\n"))
                    for code, value in zip(f, f)
                ]
        except OSError:
            return ToolResult(False, "cannot read drawing")
        entities: dict[str, int] = {}
        layers: set[str] = set()
        extmin = extmax = None
        section = None
        expect_section = False
        pending_code = None
        header_var = None
        for code, value in pairs:
            word = value.strip().upper()
            if code == "0":
                if word == "SECTION":
                    expect_section = True
                    continue
                if word == "ENDSEC":
                    section = None
                    header_var = None
                    continue
                if section == "ENTITIES":
                    if word not in ("SEQEND",):
                        entities[word] = entities.get(word, 0) + 1
                elif section == "TABLES" and word == "LAYER":
                    pending_code = "LAYER"
                continue
            if code == "2" and expect_section:
                section = word
                expect_section = False
                header_var = None
                continue
            if code == "8" and section in ("ENTITIES", "BLOCKS"):
                layers.add(value.strip())
            if pending_code == "LAYER" and code == "2":
                layers.add(value.strip())
                pending_code = None
            if section == "HEADER" and code == "9":
                header_var = value.strip()
            if (
                section == "HEADER"
                and header_var in ("$EXTMIN", "$EXTMAX")
                and code in ("10", "20", "30")
            ):
                slot = "min" if header_var == "$EXTMIN" else "max"
                if slot == "min":
                    extmin = extmin or {}
                    extmin[{"10": "x", "20": "y", "30": "z"}[code]] = value.strip()
                else:
                    extmax = extmax or {}
                    extmax[{"10": "x", "20": "y", "30": "z"}[code]] = value.strip()
        total = sum(entities.values())
        return ToolResult(
            True,
            f"{total} entities, {len(layers)} layer(s)",
            data={
                "entities_total": total,
                "entities_by_type": entities,
                "layers": sorted(layers),
                "extents": {"min": extmin, "max": extmax},
            },
        )
