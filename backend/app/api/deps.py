from __future__ import annotations

import logging
from typing import Optional, cast

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import Tenant

logger = logging.getLogger(__name__)


def get_tenant_id(
    x_tenant_slug: Optional[str] = Header(None, alias="X-Tenant-Slug"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> Optional[int]:                
    if x_tenant_slug:
        slug = x_tenant_slug.strip().lower()
        tenant = db.query(Tenant).filter(
            Tenant.slug == slug,
            Tenant.is_active == True,              
        ).first()
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with slug '{slug}' not found or is inactive.",
            )
        return cast(int, tenant.id)
                    
    if x_tenant_id:
        try:
            tid = int(x_tenant_id.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-ID header must be a valid integer.",
            )
        tenant = db.query(Tenant).filter(
            Tenant.id == tid,
            Tenant.is_active == True,              
        ).first()
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with ID {tid} not found or is inactive.",
            )
        return tid
                   
    return None
