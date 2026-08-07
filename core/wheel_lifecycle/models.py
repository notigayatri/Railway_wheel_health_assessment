from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Wheel:
    """
    Represents a railway wheel asset.
    Supports both:
    1. Demo Mode (auto-generated Asset ID)
    2. Deployment Mode (real railway metadata)
    """

    # Internal System ID (Always Present)
    asset_id: str

    # Railway Metadata (Optional)
    wheel_identifier: Optional[str] = None
    train_id: Optional[str] = None
    coach_id: Optional[str] = None
    axle_number: Optional[int] = None
    position: Optional[str] = None  # Left / Right

    # Current Wheel Status
    status: str = "Healthy"

    # Inspection Information
    inspection_count: int = 0
    latest_inspection: Optional[str] = None

    # Record Information
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Inspection:
    """
    Represents one AI inspection of a wheel.
    Each wheel can have multiple inspections over time.
    """

    # Inspection Details
    inspection_id: str
    asset_id: str

    # Image Information
    image_name: str
    image_path: str

    # Inspection Metadata
    inspection_date: datetime = field(default_factory=datetime.now)
    inspector_name: Optional[str] = None
    location: Optional[str] = None

    # AI Results
    defect_type: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[float] = None

    # Performance
    processing_time: Optional[float] = None  # seconds

    # Additional Notes
    notes: Optional[str] = None