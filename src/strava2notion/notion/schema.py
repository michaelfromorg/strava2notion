"""Notion database schema definitions."""

# Schema for strava2notion v2
# Matches the properties used in the original implementation
SCHEMA = {
    "Name": {"title": {}},
    "Type": {"select": {}},
    "Length": {"number": {"format": "number"}},  # km
    "Time": {"number": {"format": "number"}},  # hours
    "Power": {"number": {"format": "number"}},  # watts
    "Elevation": {"number": {"format": "number"}},  # meters
    "Date": {"date": {}},
    "Strava Link": {"url": {}},
    "Strava ID": {"rich_text": {}},  # For deduplication
}
