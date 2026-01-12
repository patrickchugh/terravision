"""
GCP Web & Mobile category - Firebase, App Engine, Cloud Endpoints.

Icon Resolution:
- All web/mobile resources use category icon (2-color): resource_images/gcp/category/web-mobile.png
"""

from . import _GCP


class _WebMobile(_GCP):
    _type = "web_mobile"
    _icon_dir = "resource_images/gcp/category"
    _icon = "web-mobile.png"


class Firebase(_WebMobile):
    """Firebase app development platform."""

    pass


class FirebaseHosting(_WebMobile):
    """Firebase Hosting for web apps."""

    pass


class FirebaseAuthentication(_WebMobile):
    """Firebase Authentication."""

    pass


class FirebaseCloudMessaging(_WebMobile):
    """Firebase Cloud Messaging (FCM)."""

    pass


class FirebaseRealtimeDatabase(_WebMobile):
    """Firebase Realtime Database."""

    pass


class AppEngine(_WebMobile):
    """App Engine PaaS."""

    pass


class CloudEndpoints(_WebMobile):
    """Cloud Endpoints API management."""

    pass


class IdentityPlatform(_WebMobile):
    """Identity Platform for authentication."""

    pass


class reCAPTCHA(_WebMobile):
    """reCAPTCHA Enterprise bot protection."""

    pass


# Aliases
Hosting = FirebaseHosting
Auth = FirebaseAuthentication
FCM = FirebaseCloudMessaging
RTDB = FirebaseRealtimeDatabase

# Terraform resource aliases
google_firebase_project = Firebase
google_firebase_web_app = Firebase
google_firebase_android_app = Firebase
google_firebase_apple_app = Firebase
google_firebase_hosting_site = FirebaseHosting
google_firebase_hosting_channel = FirebaseHosting
google_identity_platform_config = IdentityPlatform
google_identity_platform_tenant = IdentityPlatform
google_recaptcha_enterprise_key = reCAPTCHA
