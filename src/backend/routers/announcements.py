"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def serialize_announcement(announcement: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    return {
        "id": str(announcement["_id"]),
        "title": announcement.get("title", ""),
        "message": announcement.get("message", ""),
        "start_date": announcement.get("start_date"),
        "expiration_date": announcement.get("expiration_date"),
        "created_by": announcement.get("created_by", ""),
        "created_at": announcement.get("created_at", "")
    }


def validate_date_format(date_string: str, field_name: str) -> datetime:
    """Validate and parse an ISO format date string"""
    try:
        return datetime.fromisoformat(date_string)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format"
        )


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_announcements(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Get all announcements, optionally filtering to only active ones.
    
    - active_only: If True, only returns announcements where:
        - start_date is None or in the past
        - expiration_date is in the future
    """
    now = datetime.now().isoformat()
    
    announcements = []
    for announcement in announcements_collection.find():
        serialized = serialize_announcement(announcement)
        
        if active_only:
            # Check expiration date (required field)
            if serialized["expiration_date"] and serialized["expiration_date"] < now:
                continue
            
            # Check start date (optional field)
            if serialized["start_date"] and serialized["start_date"] > now:
                continue
        
        announcements.append(serialized)
    
    return announcements


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)) -> List[Dict[str, Any]]:
    """
    Get all announcements (including expired) for management.
    Requires teacher authentication.
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    announcements = []
    for announcement in announcements_collection.find():
        announcements.append(serialize_announcement(announcement))
    
    return announcements


@router.post("")
@router.post("/")
def create_announcement(
    title: str = Query(...),
    message: str = Query(...),
    expiration_date: str = Query(...),
    start_date: Optional[str] = Query(None),
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """
    Create a new announcement. Requires teacher authentication.
    """
    # Capture current time once for consistent validation
    now = datetime.now()
    
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate expiration date
    exp_date = validate_date_format(expiration_date, "expiration date")
    if exp_date < now:
        raise HTTPException(
            status_code=400, 
            detail="Expiration date must be in the future"
        )
    
    # Validate start date if provided
    if start_date:
        validate_date_format(start_date, "start date")
    
    # Create announcement
    announcement = {
        "title": title,
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_by": teacher_username,
        "created_at": datetime.now().isoformat()
    }
    
    result = announcements_collection.insert_one(announcement)
    announcement["_id"] = result.inserted_id
    
    return serialize_announcement(announcement)


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    title: str = Query(...),
    message: str = Query(...),
    expiration_date: str = Query(...),
    start_date: Optional[str] = Query(None),
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """
    Update an existing announcement. Requires teacher authentication.
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate announcement exists
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Validate expiration date
    validate_date_format(expiration_date, "expiration date")
    
    # Validate start date if provided
    if start_date:
        validate_date_format(start_date, "start date")
    
    # Update announcement
    update_data = {
        "title": title,
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date
    }
    
    result = announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update announcement")
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": obj_id})
    return serialize_announcement(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
) -> Dict[str, str]:
    """
    Delete an announcement. Requires teacher authentication.
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate announcement exists
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Delete announcement
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Failed to delete announcement")
    
    return {"message": "Announcement deleted successfully"}
