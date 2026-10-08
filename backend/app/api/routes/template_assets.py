"""Template asset API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.templates import TemplateAssetResponse
from app.services.auth_service import AuthService
from app.services.template_asset_service import TemplateAssetService

router = APIRouter(prefix="/api/v1/template-assets", tags=["template-assets"])
bearer_scheme = HTTPBearer(auto_error=False)


def get_user_for_asset(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    access_token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Allow Bearer auth or access_token query (for <img src> preview)."""
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif access_token:
        token = access_token
    if not token:
        raise UnauthorizedError("Authentication required")
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError, TypeError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    user = AuthService(db).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    return user


@router.post("", response_model=TemplateAssetResponse, status_code=201)
async def upload_template_asset(
    file: UploadFile = File(...),
    template_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateAssetResponse:
    return await TemplateAssetService(db).upload(
        current_user,
        file,
        template_id=template_id,
    )


@router.get("/{asset_id}/content")
def get_template_asset_content(
    asset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_for_asset),
) -> Response:
    asset, content = TemplateAssetService(db).read_content(current_user, asset_id)
    return Response(
        content=content,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{asset.stored_filename}"',
        },
    )
