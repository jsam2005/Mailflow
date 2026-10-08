"""Contact file parsers for CSV and XLSX."""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from collections.abc import Iterator
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.core.exceptions import ValidationAppError
from app.services.import_service.column_mapping import json_safe


def cell_to_str(value: Any) -> str | None:
    if value is None:
        return None
    safe = json_safe(value)
    if safe is None:
        return None
    text = str(safe).strip()
    return text or None


class BaseContactFileParser(ABC):
    def __init__(self, path: Path) -> None:
        self.path = path

    @abstractmethod
    def get_columns(self, sheet: str | None = None) -> list[str]:
        ...

    @abstractmethod
    def get_preview(
        self,
        sheet: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, str | None]]:
        ...

    @abstractmethod
    def iterate_rows(
        self,
        sheet: str | None = None,
    ) -> Iterator[tuple[int, dict[str, str | None]]]:
        """Yield (1-based data row number, row dict). Header is row 1."""

    @abstractmethod
    def get_row_count(self, sheet: str | None = None) -> int:
        ...

    def get_sheets(self) -> list[str]:
        return []


class CSVContactParser(BaseContactFileParser):
    def _read_text(self) -> str:
        raw = self.path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValidationAppError(
            "We couldn't read this CSV file. Please save it as UTF-8 and try again."
        )

    def _reader(self) -> tuple[list[str], list[dict[str, str | None]]]:
        text = self._read_text()
        if not text.strip():
            raise ValidationAppError("The dataset does not contain a header row.")

        stream = StringIO(text)
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValidationAppError("The dataset does not contain a header row.")

        columns = [name.strip() for name in reader.fieldnames if name and name.strip()]
        if not columns:
            raise ValidationAppError("The dataset does not contain a header row.")

        rows: list[dict[str, str | None]] = []
        for raw in reader:
            row = {
                col: cell_to_str(raw.get(col))
                for col in columns
            }
            # Skip completely empty rows
            if any(value is not None for value in row.values()):
                rows.append(row)
        return columns, rows

    def get_columns(self, sheet: str | None = None) -> list[str]:
        columns, _ = self._reader()
        return columns

    def get_preview(
        self,
        sheet: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, str | None]]:
        _, rows = self._reader()
        return rows[:limit]

    def iterate_rows(
        self,
        sheet: str | None = None,
    ) -> Iterator[tuple[int, dict[str, str | None]]]:
        _, rows = self._reader()
        for index, row in enumerate(rows, start=2):
            yield index, row

    def get_row_count(self, sheet: str | None = None) -> int:
        _, rows = self._reader()
        return len(rows)


class XLSXContactParser(BaseContactFileParser):
    def _load(self):
        try:
            return load_workbook(
                filename=self.path,
                read_only=True,
                data_only=True,
                keep_links=False,
            )
        except Exception as exc:  # noqa: BLE001 — surface friendly message
            raise ValidationAppError(
                "We couldn't read this spreadsheet. Please confirm it is a valid XLSX file."
            ) from exc

    def get_sheets(self) -> list[str]:
        workbook = self._load()
        try:
            return list(workbook.sheetnames)
        finally:
            workbook.close()

    def _resolve_sheet(self, workbook, sheet: str | None):
        names = workbook.sheetnames
        if not names:
            raise ValidationAppError("The spreadsheet does not contain any worksheets.")
        if sheet is None:
            return workbook[names[0]]
        if sheet not in names:
            raise ValidationAppError(f"Worksheet '{sheet}' was not found.")
        return workbook[sheet]

    def _extract(self, sheet: str | None) -> tuple[list[str], list[dict[str, str | None]]]:
        workbook = self._load()
        try:
            worksheet = self._resolve_sheet(workbook, sheet)
            rows_iter = worksheet.iter_rows(values_only=True)
            try:
                header_row = next(rows_iter)
            except StopIteration as exc:
                raise ValidationAppError("The dataset does not contain a header row.") from exc

            columns: list[str] = []
            for cell in header_row:
                if cell is None:
                    continue
                name = str(cell).strip()
                if name:
                    columns.append(name)

            if not columns:
                raise ValidationAppError("The dataset does not contain a header row.")

            data_rows: list[dict[str, str | None]] = []
            for values in rows_iter:
                raw = list(values or [])
                row: dict[str, str | None] = {}
                for index, column in enumerate(columns):
                    value = raw[index] if index < len(raw) else None
                    row[column] = cell_to_str(value)
                if any(value is not None for value in row.values()):
                    data_rows.append(row)
            return columns, data_rows
        finally:
            workbook.close()

    def get_columns(self, sheet: str | None = None) -> list[str]:
        columns, _ = self._extract(sheet)
        return columns

    def get_preview(
        self,
        sheet: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, str | None]]:
        _, rows = self._extract(sheet)
        return rows[:limit]

    def iterate_rows(
        self,
        sheet: str | None = None,
    ) -> Iterator[tuple[int, dict[str, str | None]]]:
        _, rows = self._extract(sheet)
        for index, row in enumerate(rows, start=2):
            yield index, row

    def get_row_count(self, sheet: str | None = None) -> int:
        _, rows = self._extract(sheet)
        return len(rows)


def get_parser(path: Path, file_type: str) -> BaseContactFileParser:
    if file_type == "csv":
        return CSVContactParser(path)
    if file_type == "xlsx":
        return XLSXContactParser(path)
    raise ValidationAppError("The selected file must be CSV or XLSX.")
