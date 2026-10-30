# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""Exceptions for pykiwee client library."""


class KiweeError(Exception):
    """Base exception for Kiwee Broadband errors."""


class KiweeConnectionError(KiweeError):
    """Connection error to Kiwee Broadband adapter."""


class KiweeAuthError(KiweeError):
    """Authentication error with Kiwee Broadband adapter."""


class KiweeTimeoutError(KiweeError):
    """Timeout error communicating with Kiwee Broadband adapter."""


class KiweeParseError(KiweeError):
    """Error parsing response from Kiwee Broadband adapter."""
