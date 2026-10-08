"""Interactive cleanup of local development data.

Never runs in production.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.email_template import EmailTemplate
from app.models.email_test_log import EmailTestLog
from app.models.import_session import ImportSession
from app.models.oauth_state import OAuthState
from app.models.suppression import SuppressionList
from app.models.template_asset import TemplateAsset
from app.models.user import User


def main() -> int:
    settings = get_settings()
    if settings.is_production:
        print("Refusing to delete data in production.", file=sys.stderr)
        return 1

    answer = input("DELETE LOCAL DEVELOPMENT DATA? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return 0

    db = SessionLocal()
    try:
        # Delete in dependency-safe order
        for model in (
            EmailMessage,
            CampaignRecipient,
            Campaign,
            EmailTestLog,
            OAuthState,
            EmailAccount,
            TemplateAsset,
            EmailTemplate,
            ImportSession,
            Contact,
            ContactList,
            SuppressionList,
        ):
            db.execute(delete(model))
        # Keep users unless explicitly cleared
        clear_users = input("Also delete all users? [y/N] ").strip().lower() == "y"
        if clear_users:
            db.execute(delete(User))
        db.commit()
        print("Development data cleared.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
