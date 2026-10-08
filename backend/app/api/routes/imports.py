"""Contact import API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.import_session import ImportSession
from app.models.user import User
from app.schemas.contact_list import ContactListCreate
from app.schemas.imports import (
    ImportExecuteRequest,
    ImportExecuteResponse,
    ImportSessionResponse,
    ImportUploadResponse,
    ImportValidateRequest,
    ImportValidationResponse,
)
from app.services.contact_list_service import ContactListService
from app.services.import_service.service import ImportService

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


def _session_response(session: ImportSession) -> ImportSessionResponse:
    return ImportSessionResponse(
        id=session.id,
        contact_list_id=session.contact_list_id,
        contact_list_name=session.contact_list.name if session.contact_list else None,
        original_filename=session.original_filename,
        file_type=session.file_type,
        status=session.status.value if hasattr(session.status, "value") else str(session.status),
        selected_sheet=session.selected_sheet,
        total_rows=session.total_rows,
        valid_rows=session.valid_rows,
        invalid_rows=session.invalid_rows,
        duplicate_rows=session.duplicate_rows,
        missing_email_rows=session.missing_email_rows,
        imported_rows=session.imported_rows,
        skipped_rows=session.skipped_rows,
        column_mapping=session.column_mapping,
        validation_summary=session.validation_summary,
        error_message=session.error_message,
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
    )


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportUploadResponse:
    data = await ImportService(db).upload(current_user, file)
    return ImportUploadResponse(**data)


@router.get("", response_model=list[ImportSessionResponse])
def list_imports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ImportSessionResponse]:
    sessions = ImportService(db).list_history(current_user)
    return [_session_response(item) for item in sessions]


@router.get("/{import_id}", response_model=ImportSessionResponse)
def get_import(
    import_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportSessionResponse:
    session = ImportService(db).get_session(current_user, import_id)
    return _session_response(session)


@router.get("/{import_id}/preview", response_model=ImportUploadResponse)
def preview_import(
    import_id: UUID,
    sheet: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportUploadResponse:
    data = ImportService(db).preview(current_user, import_id, sheet=sheet)
    return ImportUploadResponse(**data)


@router.post("/{import_id}/validate", response_model=ImportValidationResponse)
def validate_import(
    import_id: UUID,
    body: ImportValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportValidationResponse:
    summary = ImportService(db).validate(
        current_user,
        import_id,
        column_mapping=body.column_mapping,
        sheet=body.sheet,
        contact_list_id=body.contact_list_id,
    )
    return ImportValidationResponse(**summary)


@router.post("/{import_id}/execute", response_model=ImportExecuteResponse)
def execute_import(
    import_id: UUID,
    body: ImportExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportExecuteResponse:
    from app.core.exceptions import ValidationAppError

    list_id = body.contact_list_id
    if body.new_list_name:
        created = ContactListService(db).create_contact_list(
            current_user,
            ContactListCreate(
                name=body.new_list_name,
                description=body.new_list_description,
            ),
        )
        list_id = created.id
    if list_id is None:
        raise ValidationAppError("Select an existing contact list or create a new one.")

    result = ImportService(db).execute(
        current_user,
        import_id,
        contact_list_id=list_id,
        column_mapping=body.column_mapping,
        sheet=body.sheet,
    )
    return ImportExecuteResponse(**result)


@router.post("/{import_id}/cancel", response_model=ImportSessionResponse)
def cancel_import(
    import_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportSessionResponse:
    session = ImportService(db).cancel(current_user, import_id)
    return _session_response(session)
