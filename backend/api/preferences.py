"""
User Preferences API router - Filter templates, display settings, user configurations.
"""
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from backend.core import get_db
from backend.models.fund import UserPreferences


router = APIRouter()


# ==================== Pydantic Schemas ====================

class PreferenceBase(BaseModel):
    """Base schema for user preferences."""
    pref_type: str  # filter_template, display_config
    pref_key: str   # Unique identifier
    pref_name: str  # Display name
    pref_value: str  # JSON string
    is_default: bool = False


class PreferenceCreate(PreferenceBase):
    """Schema for creating a new preference."""
    pass


class PreferenceUpdate(BaseModel):
    """Schema for updating an existing preference."""
    pref_name: Optional[str] = None
    pref_value: Optional[str] = None
    is_default: Optional[bool] = None


class PreferenceResponse(PreferenceBase):
    """Schema for preference response."""
    id: int
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PreferenceListResponse(BaseModel):
    """Schema for list of preferences."""
    total: int
    preferences: List[PreferenceResponse]


# ==================== API Endpoints ====================

@router.get("/{pref_type}", response_model=PreferenceListResponse)
async def get_preferences(
    pref_type: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = "default",
):
    """
    Get all preferences of a specific type.
    
    Args:
        pref_type: Type of preference (filter_template, display_config, etc.)
        user_id: User identifier (default: "default" for single-user mode)
    
    Returns:
        List of preferences matching the type
    """
    query = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_type == pref_type,
    ).order_by(UserPreferences.created_at.desc())
    
    result = await db.execute(query)
    preferences = result.scalars().all()
    
    return PreferenceListResponse(
        total=len(preferences),
        preferences=[PreferenceResponse.from_orm(p) for p in preferences],
    )


@router.post("/{pref_type}", response_model=PreferenceResponse)
async def create_preference(
    pref_type: str,
    preference: PreferenceCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = "default",
):
    """
    Create a new preference.
    
    Args:
        pref_type: Type of preference
        preference: Preference data
        user_id: User identifier
    
    Returns:
        Created preference
    
    Raises:
        HTTPException: If preference with same key already exists
    """
    # Check if already exists
    existing_query = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_type == pref_type,
        UserPreferences.pref_key == preference.pref_key,
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Preference '{preference.pref_key}' already exists"
        )
    
    # Validate JSON
    try:
        json.loads(preference.pref_value)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="pref_value must be valid JSON string"
        )
    
    # Create new preference
    new_pref = UserPreferences(
        user_id=user_id,
        pref_type=pref_type,
        pref_key=preference.pref_key,
        pref_name=preference.pref_name,
        pref_value=preference.pref_value,
        is_default=preference.is_default,
    )
    
    db.add(new_pref)
    await db.commit()
    await db.refresh(new_pref)
    
    return PreferenceResponse.from_orm(new_pref)


@router.get("/{pref_type}/{pref_key}", response_model=PreferenceResponse)
async def get_preference(
    pref_type: str,
    pref_key: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = "default",
):
    """
    Get a specific preference.
    
    Args:
        pref_type: Type of preference
        pref_key: Unique key of the preference
        user_id: User identifier
    
    Returns:
        Preference data
    
    Raises:
        HTTPException: If preference not found
    """
    query = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_type == pref_type,
        UserPreferences.pref_key == pref_key,
    )
    
    result = await db.execute(query)
    preference = result.scalar_one_or_none()
    
    if not preference:
        raise HTTPException(
            status_code=404,
            detail=f"Preference '{pref_key}' not found"
        )
    
    return PreferenceResponse.from_orm(preference)


@router.put("/{pref_type}/{pref_key}", response_model=PreferenceResponse)
async def update_preference(
    pref_type: str,
    pref_key: str,
    preference: PreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = "default",
):
    """
    Update a specific preference.
    
    Args:
        pref_type: Type of preference
        pref_key: Unique key of the preference
        preference: Updated preference data
        user_id: User identifier
    
    Returns:
        Updated preference
    
    Raises:
        HTTPException: If preference not found
    """
    query = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_type == pref_type,
        UserPreferences.pref_key == pref_key,
    )
    
    result = await db.execute(query)
    existing_pref = result.scalar_one_or_none()
    
    if not existing_pref:
        raise HTTPException(
            status_code=404,
            detail=f"Preference '{pref_key}' not found"
        )
    
    # Update fields
    if preference.pref_name is not None:
        existing_pref.pref_name = preference.pref_name
    
    if preference.pref_value is not None:
        # Validate JSON
        try:
            json.loads(preference.pref_value)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="pref_value must be valid JSON string"
            )
        existing_pref.pref_value = preference.pref_value
    
    if preference.is_default is not None:
        # If setting as default, unset other defaults of same type
        if preference.is_default:
            default_query = select(UserPreferences).where(
                UserPreferences.user_id == user_id,
                UserPreferences.pref_type == pref_type,
                UserPreferences.is_default == True,
            )
            default_result = await db.execute(default_query)
            for default_pref in default_result.scalars().all():
                default_pref.is_default = False
        
        existing_pref.is_default = preference.is_default
    
    existing_pref.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(existing_pref)
    
    return PreferenceResponse.from_orm(existing_pref)


@router.delete("/{pref_type}/{pref_key}")
async def delete_preference(
    pref_type: str,
    pref_key: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = "default",
):
    """
    Delete a specific preference.
    
    Args:
        pref_type: Type of preference
        pref_key: Unique key of the preference
        user_id: User identifier
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If preference not found
    """
    query = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_type == pref_type,
        UserPreferences.pref_key == pref_key,
    )
    
    result = await db.execute(query)
    existing_pref = result.scalar_one_or_none()
    
    if not existing_pref:
        raise HTTPException(
            status_code=404,
            detail=f"Preference '{pref_key}' not found"
        )
    
    await db.delete(existing_pref)
    await db.commit()
    
    return {"message": f"Preference '{pref_key}' deleted successfully"}


@router.post("/{pref_type}/{pref_key}/set-default")
async def set_default_preference(
    pref_type: str,
    pref_key: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = "default",
):
    """
    Set a preference as the default for its type.
    Unsets any existing default.
    
    Args:
        pref_type: Type of preference
        pref_key: Unique key of the preference
        user_id: User identifier
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If preference not found
    """
    query = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_type == pref_type,
        UserPreferences.pref_key == pref_key,
    )
    
    result = await db.execute(query)
    existing_pref = result.scalar_one_or_none()
    
    if not existing_pref:
        raise HTTPException(
            status_code=404,
            detail=f"Preference '{pref_key}' not found"
        )
    
    # Unset all defaults of same type
    default_query = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_type == pref_type,
        UserPreferences.is_default == True,
    )
    default_result = await db.execute(default_query)
    for default_pref in default_result.scalars().all():
        default_pref.is_default = False
    
    # Set new default
    existing_pref.is_default = True
    existing_pref.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": f"Preference '{pref_key}' set as default"}
