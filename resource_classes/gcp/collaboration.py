"""
GCP Collaboration category - Google Workspace, Chat, Meet.

Icon Resolution:
- All collaboration resources use category icon (2-color): resource_images/gcp/category/collaboration.png
"""

from . import _GCP


class _Collaboration(_GCP):
    _type = "collaboration"
    _icon_dir = "resource_images/gcp/category"
    _icon = "collaboration.png"


class GoogleWorkspace(_Collaboration):
    """Google Workspace (formerly G Suite)."""

    pass


class GoogleChat(_Collaboration):
    """Google Chat messaging."""

    pass


class GoogleMeet(_Collaboration):
    """Google Meet video conferencing."""

    pass


class GoogleDrive(_Collaboration):
    """Google Drive file storage."""

    pass


class GoogleDocs(_Collaboration):
    """Google Docs document editing."""

    pass


class GoogleSheets(_Collaboration):
    """Google Sheets spreadsheets."""

    pass


class GoogleSlides(_Collaboration):
    """Google Slides presentations."""

    pass


class GoogleCalendar(_Collaboration):
    """Google Calendar scheduling."""

    pass


class GoogleGroups(_Collaboration):
    """Google Groups for teams."""

    pass


# Aliases
Workspace = GoogleWorkspace
Chat = GoogleChat
Meet = GoogleMeet
Drive = GoogleDrive

# No direct Terraform resources - Workspace managed via Admin SDK
