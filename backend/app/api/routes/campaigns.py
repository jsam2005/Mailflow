"""Campaign planning API routes (no sending)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignListResponse,
    CampaignPreviewRequest,
    CampaignPreviewResponse,
    CampaignResponse,
    CampaignReviewResponse,
    CampaignStatsResponse,
    CampaignUpdate,
    CampaignValidationResponse,
    PaginatedRecipientsResponse,
    RecipientSnapshotRequest,
    RecipientSnapshotResponse,
)
from app.schemas.email_messages import EmailMessageResponse, PaginatedEmailMessagesResponse
from app.services.campaign_delivery_service import CampaignDeliveryService
from app.services.campaign_service import CampaignService

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignListResponse:
    if sort_by not in {"created_at", "updated_at", "name", "status"}:
        sort_by = "updated_at"
    if sort_order.lower() not in {"asc", "desc"}:
        sort_order = "desc"
    return CampaignService(db).list_campaigns(
        current_user,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order.lower(),
    )


@router.post("", response_model=CampaignResponse, status_code=201)
def create_campaign(
    body: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignService(db).create(current_user, body)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignService(db).get(current_user, campaign_id)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: UUID,
    body: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignService(db).update(current_user, campaign_id, body)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    CampaignService(db).delete_draft(current_user, campaign_id)


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
def cancel_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignService(db).cancel(current_user, campaign_id)


@router.post("/{campaign_id}/edit", response_model=CampaignResponse)
def return_campaign_to_draft(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignService(db).return_to_draft(current_user, campaign_id)


@router.post("/{campaign_id}/recipients/snapshot", response_model=RecipientSnapshotResponse)
def snapshot_recipients(
    campaign_id: UUID,
    body: RecipientSnapshotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecipientSnapshotResponse:
    return CampaignService(db).snapshot_recipients(current_user, campaign_id, body)


@router.get("/{campaign_id}/recipients", response_model=PaginatedRecipientsResponse)
def list_recipients(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedRecipientsResponse:
    return CampaignService(db).list_recipients(
        current_user,
        campaign_id,
        page=page,
        page_size=page_size,
        status=status,
    )


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
def campaign_stats(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignStatsResponse:
    return CampaignService(db).get_stats(current_user, campaign_id)


@router.post("/{campaign_id}/validate", response_model=CampaignValidationResponse)
def validate_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignValidationResponse:
    return CampaignService(db).validate(current_user, campaign_id)


@router.post("/{campaign_id}/ready", response_model=CampaignResponse)
def mark_campaign_ready(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignService(db).mark_ready(current_user, campaign_id)


@router.post("/{campaign_id}/preview", response_model=CampaignPreviewResponse)
def preview_campaign(
    campaign_id: UUID,
    body: CampaignPreviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignPreviewResponse:
    return CampaignService(db).preview(
        current_user,
        campaign_id,
        body or CampaignPreviewRequest(),
    )


@router.get("/{campaign_id}/review", response_model=CampaignReviewResponse)
def review_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignReviewResponse:
    return CampaignService(db).review(current_user, campaign_id)


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
def start_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignDeliveryService(db).start(current_user, campaign_id)


@router.post("/{campaign_id}/personalize-queued")
def personalize_queued_messages(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Re-render subject/html/text for queued messages only (never sent)."""
    return CampaignDeliveryService(db).personalize_unsent_messages(current_user, campaign_id)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
def pause_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignDeliveryService(db).pause(current_user, campaign_id)


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
def resume_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignResponse:
    return CampaignDeliveryService(db).resume(current_user, campaign_id)


@router.get("/{campaign_id}/messages", response_model=PaginatedEmailMessagesResponse)
def list_campaign_messages(
    campaign_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedEmailMessagesResponse:
    return CampaignDeliveryService(db).list_messages(
        current_user,
        campaign_id,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
    )


@router.get("/{campaign_id}/messages/{message_id}", response_model=EmailMessageResponse)
def get_campaign_message(
    campaign_id: UUID,
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailMessageResponse:
    return CampaignDeliveryService(db).get_message(current_user, campaign_id, message_id)


@router.post("/{campaign_id}/messages/{message_id}/retry", response_model=EmailMessageResponse)
def retry_campaign_message(
    campaign_id: UUID,
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailMessageResponse:
    return CampaignDeliveryService(db).retry_message(current_user, campaign_id, message_id)
