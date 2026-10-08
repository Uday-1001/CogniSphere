from __future__ import annotations
import logging
import re
import uuid
from typing import Optional, cast
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import Tenant

logger = logging.getLogger(__name__)

SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def get_tenant_id(
    x_tenant_slug: Optional[str] = Header(None, alias="X-Tenant-Slug"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> Optional[int]:
    if x_tenant_slug:
        slug = x_tenant_slug.strip().lower()
        if not SLUG_REGEX.match(slug):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tenant slug format: '{slug}'.",
            )

        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if tenant is None:
            logger.info(f"Auto-provisioning tenant workspace for slug '{slug}'")
            tenant = Tenant(
                uuid=str(uuid.uuid4()),
                name=f"Workspace ({slug})",
                slug=slug,
                is_active=True,
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        elif not tenant.is_active:
            tenant.is_active = True  # type: ignore
            db.commit()
            db.refresh(tenant)

        return cast(int, tenant.id)

    if x_tenant_id:
        try:
            tid = int(x_tenant_id.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-ID header must be a valid integer.",
            )
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with ID {tid} not found.",
            )
        if not tenant.is_active:
            tenant.is_active = True  # type: ignore
            db.commit()
            db.refresh(tenant)
        return tid

    return None
