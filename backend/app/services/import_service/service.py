"""Contact import orchestration service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.contact import Contact, ContactStatus
from app.models.contact_list import ContactList
from app.models.import_session import ImportSession, ImportSessionStatus
from app.models.user import User
from app.services.contact_list_service import ContactListService
from app.services.import_service.column_mapping import suggest_column_mapping, validate_mapping
from app.services.import_service.parsers import get_parser
from app.services.import_service.validation import ImportValidationService, MappedContactRow
from app.services.storage.local import LocalStorage

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".csv": "csv", ".xlsx": "xlsx"}


class ImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage = LocalStorage()
        self.list_service = ContactListService(db)
        self.validator = ImportValidationService(db)

    async def upload(self, user: User, file: UploadFile) -> dict:
        if not file.filename:
            raise ValidationAppError("A file is required.")

        original = Path(file.filename).name
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValidationAppError("The selected file must be CSV or XLSX.")

        content = await file.read()
        if not content:
            raise ValidationAppError("The uploaded file is empty.")
        if len(content) > self.settings.max_import_file_bytes:
            raise ValidationAppError(
                f"File exceeds the {self.settings.max_import_file_mb} MB import limit."
            )

        file_type = ALLOWED_EXTENSIONS[suffix]
        stored = self.storage.save_import_file(content, file_type)
        path = self.storage.import_file_path(stored)

        try:
            parser = get_parser(path, file_type)
            sheets = parser.get_sheets() if file_type == "xlsx" else []
            default_sheet = sheets[0] if sheets else None
            columns = parser.get_columns(default_sheet)
            preview = parser.get_preview(default_sheet, limit=20)
            total_rows = parser.get_row_count(default_sheet)
        except ValidationAppError:
            path.unlink(missing_ok=True)
            raise
        except Exception as exc:  # noqa: BLE001
            path.unlink(missing_ok=True)
            logger.exception("import.parse_failed", error_type=type(exc).__name__)
            raise ValidationAppError(
                "We couldn't read this file. Please confirm it is a valid CSV or XLSX."
            ) from exc

        session = ImportSession(
            user_id=user.id,
            original_filename=original,
            stored_filename=stored,
            file_type=file_type,
            status=ImportSessionStatus.UPLOADED.value,
            selected_sheet=default_sheet,
            total_rows=total_rows,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            "import.uploaded",
            import_session_id=str(session.id),
            user_id=str(user.id),
            total_rows=total_rows,
            file_type=file_type,
        )

        return {
            "import_session_id": session.id,
            "original_filename": original,
            "file_type": file_type,
            "total_rows": total_rows,
            "columns": columns,
            "preview_rows": preview,
            "suggested_mapping": suggest_column_mapping(columns),
            "sheets": sheets,
            "default_sheet": default_sheet,
            "status": self._status_value(session.status),
        }

    def preview(self, user: User, import_id: UUID, sheet: str | None = None) -> dict:
        session = self._get_owned(user, import_id)
        path = self.storage.import_file_path(session.stored_filename)
        parser = get_parser(path, session.file_type)
        selected = sheet or session.selected_sheet
        if session.file_type == "xlsx" and sheet:
            session.selected_sheet = sheet
            self.db.commit()

        columns = parser.get_columns(selected)
        preview = parser.get_preview(selected, limit=20)
        total_rows = parser.get_row_count(selected)
        session.total_rows = total_rows
        self.db.commit()

        return {
            "import_session_id": session.id,
            "original_filename": session.original_filename,
            "file_type": session.file_type,
            "total_rows": total_rows,
            "columns": columns,
            "preview_rows": preview,
            "suggested_mapping": suggest_column_mapping(columns),
            "sheets": parser.get_sheets(),
            "default_sheet": selected,
            "status": self._status_value(session.status),
        }

    def validate(
        self,
        user: User,
        import_id: UUID,
        column_mapping: dict[str, str],
        sheet: str | None = None,
        contact_list_id: UUID | None = None,
    ) -> dict:
        session = self._get_owned(user, import_id)
        if self._status_value(session.status) in {
            ImportSessionStatus.COMPLETED.value,
            ImportSessionStatus.CANCELLED.value,
            ImportSessionStatus.IMPORTING.value,
        }:
            raise ValidationAppError("This import session can no longer be validated.")

        validate_mapping(column_mapping)
        if contact_list_id:
            self.list_service.get_contact_list(user, contact_list_id)

        selected = sheet or session.selected_sheet
        path = self.storage.import_file_path(session.stored_filename)
        parser = get_parser(path, session.file_type)
        rows = list(parser.iterate_rows(selected))

        result = self.validator.validate_rows(rows, column_mapping, contact_list_id)

        cache = {
            "importable": [self._serialize_mapped(r) for r in result.importable],
            "summary": result.summary_dict(),
            "mapping": column_mapping,
            "sheet": selected,
            "contact_list_id": str(contact_list_id) if contact_list_id else None,
        }
        cache_path = self.storage.validation_cache_path(str(session.id))
        cache_path.write_text(json.dumps(cache), encoding="utf-8")

        session.column_mapping = column_mapping
        session.selected_sheet = selected
        session.contact_list_id = contact_list_id
        session.total_rows = result.total_rows
        session.valid_rows = result.importable_rows
        session.invalid_rows = result.invalid_email_rows
        session.duplicate_rows = (
            result.duplicate_in_file_rows + result.duplicate_existing_rows
        )
        session.missing_email_rows = result.missing_email_rows
        session.skipped_rows = result.skipped_rows
        session.validation_summary = result.summary_dict()
        session.status = ImportSessionStatus.VALIDATED.value
        session.error_message = None
        self.db.commit()

        logger.info(
            "import.validation_completed",
            import_session_id=str(session.id),
            user_id=str(user.id),
            importable_rows=result.importable_rows,
            total_rows=result.total_rows,
        )
        return result.summary_dict()

    def execute(
        self,
        user: User,
        import_id: UUID,
        contact_list_id: UUID,
        column_mapping: dict[str, str] | None = None,
        sheet: str | None = None,
    ) -> dict:
        session = self._get_owned(user, import_id)
        status = self._status_value(session.status)
        if status == ImportSessionStatus.CANCELLED.value:
            raise ValidationAppError("This import was cancelled.")
        if status == ImportSessionStatus.COMPLETED.value:
            raise ValidationAppError("This import has already been completed.")

        contact_list = self.list_service.get_contact_list(user, contact_list_id)
        mapping = column_mapping or session.column_mapping or {}
        validate_mapping(mapping)
        selected = sheet or session.selected_sheet

        # Always re-validate server-side before insert
        path = self.storage.import_file_path(session.stored_filename)
        parser = get_parser(path, session.file_type)
        rows = list(parser.iterate_rows(selected))
        result = self.validator.validate_rows(rows, mapping, contact_list_id)

        if result.importable_rows == 0:
            session.status = ImportSessionStatus.VALIDATED.value
            session.validation_summary = result.summary_dict()
            session.valid_rows = 0
            session.skipped_rows = result.skipped_rows
            self.db.commit()
            raise ValidationAppError("No valid contacts are available for import.")

        session.status = ImportSessionStatus.IMPORTING.value
        session.contact_list_id = contact_list.id
        session.column_mapping = mapping
        session.selected_sheet = selected
        self.db.commit()

        logger.info(
            "import.execution_started",
            import_session_id=str(session.id),
            user_id=str(user.id),
            importable_rows=result.importable_rows,
        )

        try:
            imported = self._bulk_insert(contact_list.id, result.importable)
            contact_list.total_contacts = (contact_list.total_contacts or 0) + imported
            session.imported_rows = imported
            session.valid_rows = result.importable_rows
            session.invalid_rows = result.invalid_email_rows
            session.missing_email_rows = result.missing_email_rows
            session.duplicate_rows = (
                result.duplicate_in_file_rows + result.duplicate_existing_rows
            )
            session.skipped_rows = result.skipped_rows
            session.total_rows = result.total_rows
            session.validation_summary = result.summary_dict()
            session.status = ImportSessionStatus.COMPLETED.value
            session.completed_at = datetime.now(UTC)
            session.error_message = None
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            session = self._get_owned(user, import_id)
            session.status = ImportSessionStatus.FAILED.value
            session.error_message = "Import failed unexpectedly. No partial results were committed."
            self.db.commit()
            logger.exception(
                "import.failed",
                import_session_id=str(import_id),
                user_id=str(user.id),
            )
            raise ValidationAppError(
                "Import failed unexpectedly. Please try again."
            ) from exc

        logger.info(
            "import.completed",
            import_session_id=str(session.id),
            user_id=str(user.id),
            imported_rows=imported,
            skipped_rows=result.skipped_rows,
        )

        return {
            "import_session_id": session.id,
            "contact_list_id": contact_list.id,
            "contact_list_name": contact_list.name,
            "status": self._status_value(session.status),
            "imported_rows": imported,
            "skipped_rows": result.skipped_rows,
            "total_rows": result.total_rows,
            "invalid_email_rows": result.invalid_email_rows,
            "missing_email_rows": result.missing_email_rows,
            "duplicate_in_file_rows": result.duplicate_in_file_rows,
            "duplicate_existing_rows": result.duplicate_existing_rows,
        }

    def cancel(self, user: User, import_id: UUID) -> ImportSession:
        session = self._get_owned(user, import_id)
        if self._status_value(session.status) in {
            ImportSessionStatus.COMPLETED.value,
            ImportSessionStatus.IMPORTING.value,
        }:
            raise ValidationAppError("This import can no longer be cancelled.")
        session.status = ImportSessionStatus.CANCELLED.value
        self.db.commit()
        self.db.refresh(session)
        logger.info(
            "import.cancelled",
            import_session_id=str(session.id),
            user_id=str(user.id),
        )
        return session

    def list_history(self, user: User) -> list[ImportSession]:
        stmt = (
            select(ImportSession)
            .options(joinedload(ImportSession.contact_list))
            .where(ImportSession.user_id == user.id)
            .order_by(ImportSession.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_session(self, user: User, import_id: UUID) -> ImportSession:
        return self._get_owned(user, import_id, with_list=True)

    def _bulk_insert(self, list_id: UUID, rows: list[MappedContactRow]) -> int:
        batch_size = self.settings.import_batch_size
        total = 0
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]
            objects = [
                Contact(
                    contact_list_id=list_id,
                    email=row.email or "",
                    normalized_email=row.normalized_email or "",
                    first_name=row.first_name,
                    last_name=row.last_name,
                    company=row.company,
                    phone=row.phone,
                    website=row.website,
                    status=ContactStatus.ACTIVE,
                    contact_metadata=row.metadata or {},
                )
                for row in chunk
            ]
            self.db.add_all(objects)
            self.db.flush()
            total += len(objects)
        return total

    def _get_owned(
        self,
        user: User,
        import_id: UUID,
        with_list: bool = False,
    ) -> ImportSession:
        stmt = select(ImportSession).where(
            ImportSession.id == import_id,
            ImportSession.user_id == user.id,
        )
        if with_list:
            stmt = stmt.options(joinedload(ImportSession.contact_list))
        session = self.db.scalar(stmt)
        if session is None:
            raise NotFoundError("Import session not found")
        return session

    @staticmethod
    def _serialize_mapped(row: MappedContactRow) -> dict:
        return {
            "row_number": row.row_number,
            "email": row.email,
            "normalized_email": row.normalized_email,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "company": row.company,
            "phone": row.phone,
            "website": row.website,
            "metadata": row.metadata,
        }

    @staticmethod
    def _status_value(status: ImportSessionStatus | str) -> str:
        return status.value if isinstance(status, ImportSessionStatus) else str(status)
