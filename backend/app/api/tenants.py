from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantCreate(BaseModel):
    name: str
    slug: str

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError(
                "Slug must be lowercase alphanumeric words separated by hyphens "
                "(e.g. 'acme-corp')."
            )
        return v


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    id: int
    uuid: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    """Provision a new tenant workspace."""
    existing = db.query(Tenant).filter(Tenant.slug == payload.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tenant with slug '{payload.slug}' already exists.",
        )
    tenant = Tenant(
        uuid=str(uuid.uuid4()),
        name=payload.name.strip(),
        slug=payload.slug,
        is_active=True,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(db: Session = Depends(get_db)):
    """Return all tenants (active and inactive)."""
    return db.query(Tenant).order_by(Tenant.created_at.desc()).all()


@router.get("/{slug}", response_model=TenantResponse)
async def get_tenant(slug: str, db: Session = Depends(get_db)):
    """Return a single tenant by its slug."""
    tenant = db.query(Tenant).filter(Tenant.slug == slug.strip().lower()).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{slug}' not found.",
        )
    return tenant


@router.patch("/{slug}", response_model=TenantResponse)
async def update_tenant(slug: str, payload: TenantUpdate, db: Session = Depends(get_db)):
    """Update a tenant's display name or active status."""
    tenant = db.query(Tenant).filter(Tenant.slug == slug.strip().lower()).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{slug}' not found.",
        )
    if payload.name is not None:
        tenant.name = payload.name.strip()  # type: ignore
    if payload.is_active is not None:
        tenant.is_active = payload.is_active  # type: ignore
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{slug}", status_code=status.HTTP_200_OK)
async def deactivate_tenant(slug: str, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.slug == slug.strip().lower()).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{slug}' not found.",
        )
    tenant.is_active = False  # type: ignore
    db.commit()
    return {
        "message": f"Tenant '{slug}' has been deactivated. "
                   "Existing data is retained but the tenant cannot be resolved in new requests."
    }
