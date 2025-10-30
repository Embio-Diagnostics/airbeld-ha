"""Config flow for Airbeld integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import config_entry_oauth2_flow

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant
    from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_CLIENT_ID,
    OAUTH2_TOKEN,
)

_LOGGER = logging.getLogger(__name__)


async def async_register_implementation(hass: HomeAssistant) -> None:
    """
    Register the OAuth2 implementation if not already registered.

    This ensures the implementation is available even if async_setup
    hasn't been called yet, which can happen when adding the integration
    for the first time through the UI.
    """
    # Check if implementation already exists by getting the dict of implementations
    implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )

    if implementations:
        _LOGGER.debug("OAuth2 implementation already registered")
        return

    # Implementation doesn't exist, register it now
    _LOGGER.debug("Registering OAuth2 implementation")
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            client_id=OAUTH2_CLIENT_ID,
            client_secret=None,  # PKCE flow - no secret needed
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        ),
    )


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Airbeld OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": "openid profile email offline_access",
            "audience": "https://airbeld-drf/api",
            "code_challenge_method": "S256",  # PKCE SHA-256 method
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle a flow initialized by the user.

        Ensure OAuth2 implementation is registered before proceeding.
        """
        # Ensure OAuth2 implementation is registered
        await async_register_implementation(self.hass)

        # Continue with standard OAuth2 flow
        return await super().async_step_user(user_input)

    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle implementation picking.

        Ensure OAuth2 implementation is registered before the base class checks for it.
        """
        # Ensure OAuth2 implementation is registered before base class tries to find it
        await async_register_implementation(self.hass)

        # Continue with standard implementation picking flow
        return await super().async_step_pick_implementation(user_input)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for Airbeld."""
        # Store the full OAuth2 token data for refresh capability
        return self.async_create_entry(
            title="Airbeld",
            data=data,
        )
