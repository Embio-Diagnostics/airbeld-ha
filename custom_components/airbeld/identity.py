"""Account and registry identities, with server-authenticated subjects."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import jwt
from aiohttp import ClientError
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import const

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

AUTH_REQUIRED = "Sign in to airbeld again"
IDENTITY_UNAVAILABLE = "Identity service unavailable"
MISSING_SUBJECT = "Identity service returned no subject"
ISSUER = "https://auth.embiodiagnostics.eu/"
AUDIENCE = "https://airbeld-drf/api"


def environment(data: Mapping[str, Any]) -> str:
    """Retain the API origin at sign-in, including for development installs."""
    return data.get("environment", const.DEFAULT_API_BASE).rstrip("/")


def account_id(env: str, sub: str) -> str:
    """Use an unambiguous tuple encoding, even for subjects containing separators."""
    return json.dumps([env, sub], separators=(",", ":"))


def device_identifier(env: str, sub: str, uid: str) -> str:
    """Encode environment, subject and uid as an account-owned device identity."""
    return json.dumps([env, sub, uid], separators=(",", ":"))


def sensor_unique_id(env: str, sub: str, uid: str, key: str) -> str:
    """Encode account, device and sensor key without ambiguous separators."""
    return json.dumps([env, sub, uid, key], separators=(",", ":"))


async def async_subject(hass: HomeAssistant, token: str) -> str:
    """Authenticate the bearer with Auth0 userinfo, not unverified JWT claims."""
    try:
        async with async_get_clientsession(hass).get(
            "https://auth.embiodiagnostics.eu/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        ) as response:
            if response.status in (401, 403):
                raise ConfigEntryAuthFailed(AUTH_REQUIRED)
            if response.status != HTTPStatus.OK:
                raise ConfigEntryNotReady(IDENTITY_UNAVAILABLE)
            data = await response.json()
    except (ClientError, TimeoutError, ValueError) as err:
        raise ConfigEntryNotReady(IDENTITY_UNAVAILABLE) from err
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("sub"), str)
        or not data["sub"]
    ):
        raise ConfigEntryAuthFailed(MISSING_SUBJECT)
    return data["sub"]


async def async_legacy_subject(hass: HomeAssistant, token: str) -> str:
    """
    Recover legacy account identity from a signed, possibly expired API JWT.

    Expiration is ignored only to bind the old registry to its original subject;
    this never authorizes an API call. Signature, issuer and audience still apply.
    """
    try:
        async with async_get_clientsession(hass).get(
            ISSUER + ".well-known/jwks.json", timeout=30
        ) as response:
            if response.status != HTTPStatus.OK:
                raise ConfigEntryNotReady(IDENTITY_UNAVAILABLE)
            keys = await response.json()
        header = jwt.get_unverified_header(token)
        key = next(
            key
            for key in jwt.PyJWKSet.from_dict(keys).keys
            if key.key_id == header.get("kid")
        )
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"verify_exp": False, "require": ["sub", "iss", "aud"]},
        )
    except (ClientError, TimeoutError, ValueError) as err:
        raise ConfigEntryNotReady(IDENTITY_UNAVAILABLE) from err
    except (jwt.PyJWTError, StopIteration) as err:
        raise ConfigEntryAuthFailed(MISSING_SUBJECT) from err
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise ConfigEntryAuthFailed(MISSING_SUBJECT)
    return claims["sub"]
