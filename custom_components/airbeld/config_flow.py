"""Config flow for Airbeld integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
from .identity import account_id, async_legacy_subject, async_subject, environment

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
        config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(
            hass,
            DOMAIN,
            client_id=OAUTH2_CLIENT_ID,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        ),
    )


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Airbeld OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 2

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

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:  # noqa: PLR0911 — explicit identity/auth/connectivity aborts
        """Create an entry for Airbeld."""
        try:
            sub = await async_subject(self.hass, data["token"]["access_token"])
        except ConfigEntryAuthFailed:
            return self.async_abort(reason="oauth_error")
        except ConfigEntryNotReady:
            return self.async_abort(reason="cannot_connect")
        if self.source == "reauth":
            entry = self._get_reauth_entry()
            env = environment(entry.data)
            original_sub = entry.data.get("sub")
            if not original_sub:
                try:
                    original_sub = await async_legacy_subject(
                        self.hass, entry.data["token"]["access_token"]
                    )
                except ConfigEntryAuthFailed:
                    return self.async_abort(reason="oauth_error")
                except ConfigEntryNotReady:
                    return self.async_abort(reason="cannot_connect")
            if original_sub != sub:
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(
                entry, data_updates={**data, "sub": original_sub, "environment": env}
            )
        env = environment(data)
        await self.async_set_unique_id(account_id(env, sub))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Airbeld",
            data={**data, "environment": env, "sub": sub},
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Use the original account's OAuth implementation; never reconfigure it."""
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm before starting another authorization for the original entry."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_pick_implementation(
            {"implementation": self._get_reauth_entry().data["auth_implementation"]}
        )
