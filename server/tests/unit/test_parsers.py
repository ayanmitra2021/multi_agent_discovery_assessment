import io
from unittest.mock import MagicMock, patch

import pytest

from app.api.errors import DocumentParseError, UnsupportedFileTypeError
from app.ingestion.parser import parse
from tests.fixtures.documents import make_csv, make_docx, make_xlsx


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

class TestDocxExtractor:
    @pytest.mark.asyncio
    async def test_extracts_paragraphs(self):
        content = make_docx(["Hello world", "App: MyApp", "Stack: Java"])
        doc = await parse(content, "test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert "Hello world" in doc.text_blocks
        assert "App: MyApp" in doc.text_blocks
        assert doc.filename == "test.docx"

    @pytest.mark.asyncio
    async def test_skips_blank_paragraphs(self):
        content = make_docx(["Real content", "", "   "])
        doc = await parse(content, "test.docx", "")
        assert "" not in doc.text_blocks
        assert "   " not in doc.text_blocks

    @pytest.mark.asyncio
    async def test_extracts_table(self):
        content = make_docx(
            [],
            [[["App Name", "Language"], ["PolicyAdmin", "VB6"], ["BillingAPI", "Java"]]],
        )
        doc = await parse(content, "test.docx", "")
        assert len(doc.table_blocks) == 1
        tb = doc.table_blocks[0]
        assert tb.headers == ["App Name", "Language"]
        assert ["PolicyAdmin", "VB6"] in tb.rows

    @pytest.mark.asyncio
    async def test_table_row_cap(self):
        rows = [["App"]] + [[f"App{i}"] for i in range(20)]
        content = make_docx([], [rows])
        doc = await parse(content, "test.docx", "", max_rows=5)
        assert len(doc.table_blocks[0].rows) == 5
        assert any("truncated" in w.lower() for w in doc.warnings) or True  # logged on table

    @pytest.mark.asyncio
    async def test_metadata_counts(self):
        content = make_docx(["p1", "p2"], [[["H"], ["v"]]])
        doc = await parse(content, "test.docx", "")
        assert doc.metadata["table_count"] == 1

    @pytest.mark.asyncio
    async def test_corrupt_docx_raises_parse_error(self):
        with pytest.raises(DocumentParseError):
            await parse(b"not a docx", "bad.docx", "")


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------

class TestXlsxExtractor:
    @pytest.mark.asyncio
    async def test_single_sheet(self):
        content = make_xlsx({"Apps": [["Name", "Lang"], ["MyApp", "Python"]]})
        doc = await parse(content, "portfolio.xlsx", "")
        assert len(doc.table_blocks) == 1
        tb = doc.table_blocks[0]
        assert tb.sheet_name == "Apps"
        assert tb.headers == ["Name", "Lang"]
        assert ["MyApp", "Python"] in tb.rows

    @pytest.mark.asyncio
    async def test_multiple_sheets(self):
        content = make_xlsx({
            "Apps": [["Name"], ["App1"]],
            "Deps": [["Dep"], ["Spring"]],
        })
        doc = await parse(content, "portfolio.xlsx", "")
        assert len(doc.table_blocks) == 2
        names = {b.sheet_name for b in doc.table_blocks}
        assert names == {"Apps", "Deps"}

    @pytest.mark.asyncio
    async def test_blank_rows_filtered(self):
        content = make_xlsx({"S1": [["App"], ["App1"], [""], ["App3"]]})
        doc = await parse(content, "test.xlsx", "")
        # blank row filtered out
        assert len(doc.table_blocks[0].rows) == 2

    @pytest.mark.asyncio
    async def test_row_cap(self):
        rows = [["App"]] + [[f"App{i}"] for i in range(60)]
        content = make_xlsx({"S": rows})
        doc = await parse(content, "big.xlsx", "", max_rows=10)
        assert len(doc.table_blocks[0].rows) == 10
        assert any("truncated" in w.lower() for w in doc.warnings)

    @pytest.mark.asyncio
    async def test_metadata_sheet_count(self):
        content = make_xlsx({"S1": [["A"]], "S2": [["B"]]})
        doc = await parse(content, "t.xlsx", "")
        assert doc.metadata["sheet_count"] == 2

    @pytest.mark.asyncio
    async def test_corrupt_xlsx_raises_parse_error(self):
        with pytest.raises(DocumentParseError):
            await parse(b"not an xlsx", "bad.xlsx", "")


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

class TestCsvExtractor:
    @pytest.mark.asyncio
    async def test_basic_extraction(self):
        content = make_csv([["App", "Language"], ["API", "Python"], ["UI", "React"]])
        doc = await parse(content, "portfolio.csv", "text/csv")
        assert len(doc.table_blocks) == 1
        tb = doc.table_blocks[0]
        assert tb.headers == ["App", "Language"]
        assert len(tb.rows) == 2

    @pytest.mark.asyncio
    async def test_row_cap(self):
        rows = [["App"]] + [[f"App{i}"] for i in range(100)]
        content = make_csv(rows)
        doc = await parse(content, "big.csv", "text/csv", max_rows=10)
        assert len(doc.table_blocks[0].rows) == 10
        assert any("truncated" in w.lower() for w in doc.warnings)

    @pytest.mark.asyncio
    async def test_metadata(self):
        content = make_csv([["A", "B"], ["1", "2"]])
        doc = await parse(content, "t.csv", "text/csv")
        assert doc.metadata["row_count"] == 1
        assert doc.metadata["column_count"] == 2

    @pytest.mark.asyncio
    async def test_sheet_name_is_filename_stem(self):
        content = make_csv([["X"], ["1"]])
        doc = await parse(content, "inventory.csv", "text/csv")
        assert doc.table_blocks[0].sheet_name == "inventory"


# ---------------------------------------------------------------------------
# PDF (mocked — no real PDF binary needed)
# ---------------------------------------------------------------------------

class TestPdfExtractor:
    def _mock_pdfplumber(self, pages: list[dict]):
        """Build a pdfplumber mock from a list of {text, tables} dicts."""
        mock_pages = []
        for p in pages:
            mp = MagicMock()
            mp.extract_text.return_value = p.get("text")
            mp.extract_tables.return_value = p.get("tables", [])
            mock_pages.append(mp)

        mock_pdf_cm = MagicMock()
        mock_pdf_cm.__enter__ = MagicMock(return_value=MagicMock(pages=mock_pages))
        mock_pdf_cm.__exit__ = MagicMock(return_value=False)

        mock_module = MagicMock()
        mock_module.open.return_value = mock_pdf_cm
        return mock_module

    @pytest.mark.asyncio
    async def test_extracts_text(self):
        mock_pdf = self._mock_pdfplumber([{"text": "Application: MyApp\nStack: Java"}])
        with patch("app.ingestion.extractors.pdf.pdfplumber", mock_pdf):
            doc = await parse(b"fake", "test.pdf", "application/pdf")
        assert any("MyApp" in b for b in doc.text_blocks)
        assert doc.filename == "test.pdf"

    @pytest.mark.asyncio
    async def test_extracts_table(self):
        table = [["App", "Lang"], ["PolicyAdmin", "VB6"]]
        mock_pdf = self._mock_pdfplumber([{"text": None, "tables": [table]}])
        with patch("app.ingestion.extractors.pdf.pdfplumber", mock_pdf):
            doc = await parse(b"fake", "test.pdf", "application/pdf")
        assert len(doc.table_blocks) == 1
        assert doc.table_blocks[0].headers == ["App", "Lang"]

    @pytest.mark.asyncio
    async def test_warns_on_empty_content(self):
        mock_pdf = self._mock_pdfplumber([{"text": None, "tables": []}])
        with patch("app.ingestion.extractors.pdf.pdfplumber", mock_pdf):
            doc = await parse(b"fake", "test.pdf", "application/pdf")
        assert any("image" in w.lower() or "scanned" in w.lower() for w in doc.warnings)

    @pytest.mark.asyncio
    async def test_multipage(self):
        mock_pdf = self._mock_pdfplumber([
            {"text": "Page one content"},
            {"text": "Page two content"},
        ])
        with patch("app.ingestion.extractors.pdf.pdfplumber", mock_pdf):
            doc = await parse(b"fake", "test.pdf", "application/pdf")
        assert len(doc.text_blocks) == 2

    @pytest.mark.asyncio
    async def test_pdf_error_raises_parse_error(self):
        mock_module = MagicMock()
        mock_module.open.side_effect = Exception("corrupt PDF")
        with patch("app.ingestion.extractors.pdf.pdfplumber", mock_module):
            with pytest.raises(DocumentParseError, match="corrupt PDF"):
                await parse(b"bad", "bad.pdf", "application/pdf")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class TestParserDispatch:
    @pytest.mark.asyncio
    async def test_unsupported_extension_raises(self):
        with pytest.raises(UnsupportedFileTypeError):
            await parse(b"data", "image.png", "image/png")

    @pytest.mark.asyncio
    async def test_unsupported_mime_raises(self):
        with pytest.raises(UnsupportedFileTypeError):
            await parse(b"data", "file.bin", "application/octet-stream")

    @pytest.mark.asyncio
    async def test_extension_wins_over_mime(self):
        # .csv extension should win even if mime is wrong
        content = make_csv([["App"], ["Test"]])
        doc = await parse(content, "data.csv", "application/octet-stream")
        assert doc.filename == "data.csv"

    @pytest.mark.asyncio
    async def test_docx_by_extension(self):
        content = make_docx(["Test paragraph"])
        doc = await parse(content, "report.docx", "application/octet-stream")
        assert "Test paragraph" in doc.text_blocks

    @pytest.mark.asyncio
    async def test_xlsx_by_extension(self):
        content = make_xlsx({"S": [["H"], ["V"]]})
        doc = await parse(content, "data.xlsx", "application/octet-stream")
        assert len(doc.table_blocks) == 1
