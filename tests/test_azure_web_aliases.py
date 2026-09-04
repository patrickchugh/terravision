"""
Regression tests for Azure web resource aliases.

Both icons these aliases reach already ship with Terravision, but the module
could not resolve either resource:

- ``azurerm_static_site`` was renamed ``azurerm_static_web_app`` in the AzureRM
  provider, and only the old name was aliased.
- ``azurerm_cdn_frontdoor_*`` was never aliased, so ``FrontDoorAndCDNProfiles``
  was unreachable. Classic CDN is not an alternative: creating new
  ``azurerm_cdn_profile`` resources has been blocked since 1 October 2025.

Without the aliases both render as generic unconnected nodes.
"""

import pytest

from resource_classes.azure import web


class TestStaticWebAppAlias:
    def test_current_resource_name_is_aliased(self):
        assert hasattr(web, "azurerm_static_web_app")

    def test_current_name_resolves_to_static_apps_icon(self):
        assert web.azurerm_static_web_app is web.StaticApps

    def test_renamed_resource_keeps_the_legacy_alias(self):
        assert web.azurerm_static_site is web.StaticApps


class TestFrontDoorAliases:
    FRONT_DOOR_RESOURCES = [
        "azurerm_cdn_frontdoor_profile",
        "azurerm_cdn_frontdoor_endpoint",
        "azurerm_cdn_frontdoor_origin_group",
        "azurerm_cdn_frontdoor_origin",
        "azurerm_cdn_frontdoor_route",
    ]

    @pytest.mark.parametrize("resource", FRONT_DOOR_RESOURCES)
    def test_resource_is_aliased(self, resource):
        assert hasattr(web, resource)

    @pytest.mark.parametrize("resource", FRONT_DOOR_RESOURCES)
    def test_resource_resolves_to_front_door_icon(self, resource):
        assert getattr(web, resource) is web.FrontDoorAndCDNProfiles


class TestAliasedIconsExist:
    """An alias pointing at a class whose icon file is missing still renders blank."""

    @pytest.mark.parametrize(
        "icon_class", [web.StaticApps, web.FrontDoorAndCDNProfiles]
    )
    def test_icon_file_is_present(self, icon_class):
        from pathlib import Path

        icon = Path(web.__file__).parents[2] / icon_class._icon_dir / icon_class._icon
        assert icon.is_file(), f"missing icon file: {icon}"
