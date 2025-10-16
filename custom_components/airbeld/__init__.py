"""The Airbeld integration."""
from __future__ import annotations

import logging

from airbeld import AirbeldClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.typing import ConfigType

from .const import (
    DEFAULT_API_BASE,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_CLIENT_ID,
    OAUTH2_TOKEN,
)
from .coordinator import AirbeldDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Airbeld component."""
    try:
        # Register OAuth2 implementation with embedded credentials
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
        _LOGGER.debug("OAuth2 implementation registered")
    except Exception as err:
        _LOGGER.error("Failed to register OAuth2 implementation: %s", err, exc_info=True)
        # Don't fail setup - the config flow will handle registration if needed

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Airbeld from a config entry."""
    # Get OAuth2 session for token management and refresh
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    
    try:
        await session.async_ensure_token_valid()
    except Exception as err:
        _LOGGER.error("Token validation failed: %s", err)
        return False

    # Get the current access token
    access_token = session.token[CONF_ACCESS_TOKEN]

    # Create the Airbeld client in executor to avoid blocking I/O during SSL setup
    def create_client() -> AirbeldClient:
        """Create AirbeldClient with blocking operations in executor."""
        return AirbeldClient(token=access_token, base_url=DEFAULT_API_BASE)

    client = await hass.async_add_executor_job(create_client)
    
    # Create the data coordinator with OAuth2 session for token refresh
    coordinator = AirbeldDataUpdateCoordinator(hass, client, session)
    
    # Fetch initial data so we have data when we create the entities
    await coordinator.async_config_entry_first_refresh()
    
    # Store the coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Get coordinator and close client
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if hasattr(coordinator.client, 'aclose'):
            await coordinator.client.aclose()
        
        # Clean up if this was the last entry
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    
    return unload_ok