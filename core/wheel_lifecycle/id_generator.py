import json
from pathlib import Path

# Path to metadata.json
METADATA_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "database"
    / "metadata.json"
)


def _load_metadata():
    """Load metadata from JSON file."""

    with open(METADATA_FILE, "r") as file:
        return json.load(file)


def _save_metadata(metadata):
    """Save metadata back to JSON."""

    with open(METADATA_FILE, "w") as file:
        json.dump(metadata, file, indent=4)


def generate_asset_id():
    """Generate the next Wheel Asset ID."""

    metadata = _load_metadata()

    metadata["last_asset_id"] += 1

    _save_metadata(metadata)

    return f"WH{metadata['last_asset_id']:06d}"


def generate_inspection_id():
    """Generate the next Inspection ID."""

    metadata = _load_metadata()

    metadata["last_inspection_id"] += 1

    _save_metadata(metadata)

    return f"INS{metadata['last_inspection_id']:06d}"