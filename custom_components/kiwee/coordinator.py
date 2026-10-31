# Derived from hass-gocoax (Apache-2.0, https://github.com/homeassistant-projects/hass-gocoax);
# modified for Kiwee Broadband MoCA adapters. See NOTICE.
"""DataUpdateCoordinator for Kiwee Broadband MoCA integration."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    REBOOT_POLL_INTERVAL,
)
from .pykiwee import AdapterStatus, KiweeClient, RebootWatch
from .pykiwee.exceptions import (
    KiweeAuthError,
    KiweeConnectionError,
    KiweeError,
    KiweeTimeoutError,
)

if TYPE_CHECKING:
    pass

LOG = logging.getLogger(__name__)


class KiweeCoordinator(DataUpdateCoordinator[AdapterStatus]):
    """Coordinator for Kiwee Broadband MoCA adapter data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._host = entry.data[CONF_HOST]
        self._username = entry.data.get(CONF_USERNAME, DEFAULT_USERNAME)
        self._password = entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD)
        self._entry = entry

        # get scan interval from options or use default
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            LOG,
            name=f"{DOMAIN}_{self._host}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

        # create client with shared session
        session = async_get_clientsession(hass)
        self._client = KiweeClient(
            host=self._host,
            username=self._username,
            password=self._password,
            session=session,
        )

        self._consecutive_errors = 0
        self._max_consecutive_errors = 5

        self._normal_interval = timedelta(seconds=scan_interval)
        self._reboot = RebootWatch()
        self._reboot_cancel = None

    @property
    def host(self) -> str:
        """Return the host address."""
        return self._host

    @property
    def mac_address(self) -> str | None:
        """Return the MAC address if available."""
        if self.data:
            return self.data.mac_address
        return None

    @property
    def rebooting(self) -> bool:
        """True from a reboot request until the adapter answers again."""
        return self._reboot.active

    async def async_reboot(self) -> None:
        """Reboot the adapter and watch for it to come back."""
        await self._client.reboot()
        LOG.warning("Reboot requested for Kiwee Broadband at %s", self._host)
        self._consecutive_errors = 0
        self._reboot.start(time.monotonic())
        self.update_interval = timedelta(seconds=REBOOT_POLL_INTERVAL)
        if self._reboot_cancel:
            self._reboot_cancel()
        # the first probe comes once the adapter has had time to go down
        self._reboot_cancel = async_call_later(
            self.hass, self._reboot.min_wait + 1, self._async_probe_after_reboot
        )
        self.async_update_listeners()  # entities become unavailable

    async def _async_probe_after_reboot(self, _now) -> None:
        """Trigger the first update after the settling time."""
        self._reboot_cancel = None
        await self.async_request_refresh()

    def _finish_reboot(self) -> None:
        """Back to the normal update interval."""
        self.update_interval = self._normal_interval
        self.async_update_listeners()

    async def _async_update_while_rebooting(self) -> AdapterStatus:
        """Update step while the adapter restarts: quiet, no errors in the log."""
        now = time.monotonic()
        if self.data is None:
            self._reboot.started = None
            self.update_interval = self._normal_interval
            return await self._client.get_status()
        if self._reboot.settling(now):
            return self.data
        status = None
        try:
            status = await self._client.get_status()
        except KiweeError as err:
            LOG.debug("Kiwee Broadband at %s not reachable (rebooting): %s", self._host, err)
            outcome = self._reboot.on_probe(now, reachable=False)
        else:
            # right after the request the adapter still answers for a while
            outcome = self._reboot.on_probe(now, reachable=True)
        if outcome == "back":
            LOG.info("Kiwee Broadband at %s is back after the reboot", self._host)
            self._consecutive_errors = 0
            self._finish_reboot()
            return status
        if outcome == "timeout":
            self._finish_reboot()
            raise UpdateFailed(
                f"Kiwee Broadband at {self._host} did not come back after the reboot"
            )
        return status if status is not None else self.data

    async def _async_update_data(self) -> AdapterStatus:
        """Fetch data from Kiwee Broadband adapter."""
        if self._reboot.active:
            return await self._async_update_while_rebooting()
        try:
            status = await self._client.get_status()
            self._consecutive_errors = 0
            LOG.debug(
                f"Updated Kiwee Broadband data: mac={status.mac_address}, "
                f"link={status.link_status}, moca={status.moca_version}"
            )
            return status

        except KiweeAuthError as err:
            self._consecutive_errors += 1
            LOG.error(f"Authentication failed for Kiwee Broadband at {self._host}")
            raise ConfigEntryAuthFailed(
                f"Authentication failed for Kiwee Broadband adapter at {self._host}"
            ) from err

        except KiweeTimeoutError as err:
            self._consecutive_errors += 1
            LOG.warning(
                f"Timeout communicating with Kiwee Broadband at {self._host} "
                f"(error {self._consecutive_errors}/{self._max_consecutive_errors})"
            )
            if self._consecutive_errors >= self._max_consecutive_errors:
                raise UpdateFailed(
                    f"Too many consecutive timeouts for Kiwee Broadband at {self._host}"
                ) from err
            # return stale data if available
            if self.data:
                return self.data
            raise UpdateFailed(f"Timeout connecting to Kiwee Broadband at {self._host}") from err

        except KiweeConnectionError as err:
            self._consecutive_errors += 1
            LOG.warning(
                f"Connection error to Kiwee Broadband at {self._host}: {err} "
                f"(error {self._consecutive_errors}/{self._max_consecutive_errors})"
            )
            if self._consecutive_errors >= self._max_consecutive_errors:
                raise UpdateFailed(
                    f"Too many consecutive errors for Kiwee Broadband at {self._host}"
                ) from err
            # return stale data if available
            if self.data:
                return self.data
            raise UpdateFailed(f"Cannot connect to Kiwee Broadband at {self._host}") from err

        except Exception as err:
            self._consecutive_errors += 1
            LOG.exception(f"Unexpected error fetching Kiwee Broadband data from {self._host}")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._reboot_cancel:
            self._reboot_cancel()
            self._reboot_cancel = None
        await super().async_shutdown()
        # client uses shared session, don't close it
