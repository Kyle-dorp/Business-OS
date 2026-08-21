"""
Team Communication Module
Internal chat, shift notes, announcements, file sharing
"""

from sqlmodel import SQLModel, Field
from typing import Optional

class TeamChannel(SQLModel, table=True):
    """Chat channel"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    name: str
    description: str = ""
    is_private: bool = False
    created_at: str

class ChannelMessage(SQLModel, table=True):
    """Messages in channels"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    channel_id: int = Field(index=True)
    user_id: int = Field(index=True)
    message: str
    attachments_json: str = "[]"
    created_at: str = Field(index=True)
    edited_at: Optional[str] = None

class DirectMessage(SQLModel, table=True):
    """Direct messages between staff"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    sender_id: int = Field(index=True)
    recipient_id: int = Field(index=True)
    message: str
    read: bool = False
    created_at: str = Field(index=True)

class ShiftNote(SQLModel, table=True):
    """Notes left by staff for upcoming shifts"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    schedule_id: int = Field(index=True)
    shift_id: int = Field(index=True)
    note: str
    priority: str = "normal"  # low, normal, high
    created_by: int = Field(index=True)
    created_at: str

class Announcement(SQLModel, table=True):
    """Business-wide announcements"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    title: str
    message: str
    priority: str = "normal"
    created_by: int = Field(index=True)
    created_at: str = Field(index=True)
    expires_at: Optional[str] = None
    read_by_json: str = "[]"  # list of user IDs who read it

class ShiftSwapRequest(SQLModel, table=True):
    """Shift swap requests between employees"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    requester_id: int = Field(index=True)
    requested_user_id: int = Field(index=True)
    shift_id_from: int = Field(index=True)
    shift_id_to: int = Field(index=True)
    status: str = "pending"  # pending, approved, denied
    created_at: str

class FileShare(SQLModel, table=True):
    """Shared files/documents"""
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    channel_id: Optional[int] = None  # null = general
    file_name: str
    file_url: str
    file_size: int
    uploaded_by: int = Field(index=True)
    uploaded_at: str
