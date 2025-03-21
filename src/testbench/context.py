import logging
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Any

from playhouse.sqlite_ext import (  # pyright: ignore[reportMissingTypeStubs]
    SqliteExtDatabase,
)

DEFAULT_DEBUG: bool = False
NAME: str = "test-bench"
NAME_CLI: str = "testbench"

DEFAULT_SSID: str = "Kiwix Hotspot"
DEFAULT_PASSPHRASE: str = ""
DEFAULT_MAX_DEVICES: int = 0
DEFAULT_EXCLUDE_BROADCOM: bool = False
DEFAULT_ADDRESS_NETWORK: IPv4Network = IPv4Network("192.168.2.0/24")
DEFAULT_PING_ADDRESS: IPv4Address = IPv4Address("192.168.2.1")
DEFAULT_GATEWAY_ADDRESS: IPv4Address = IPv4Address("192.168.2.1")
DEFAULT_DNS_ADDRESS: IPv4Address = IPv4Address("192.168.2.1")
DEFAULT_TLD: str = "Hotspot"
DEFAULT_FLD: str = "kiwix"
DEFAULT_SVC_DOMAIN: str = "browse"
DEFAULT_ZIM_MANAGER_DOMAIN: str = "zim-manager"
DEFAULT_DNS_CAPTURED_DOMAIN_IP: IPv4Address = IPv4Address("198.51.100.1")
DEFAULT_ASSUME_ONLINE: bool = False
DEFAULT_CONTENT_ID: str = ""

DEFAULT_DB_PATH: Path = Path("testbench.db")
DEFAULT_JMX_PATH: Path = Path(__file__).parent.joinpath("perf.jmx").resolve()
DEFAULT_DHCP_TIMEOUT: int = 20


@dataclass(kw_only=True)
class Context:

    # singleton instance
    _instance: "Context | None" = None
    _db: SqliteExtDatabase | None = None

    # debug flag
    debug: bool = DEFAULT_DEBUG
    command: str

    dhcp_timeout: int = DEFAULT_DHCP_TIMEOUT

    tld: str = DEFAULT_TLD
    fld: str = DEFAULT_FLD
    svc_domain: str = DEFAULT_SVC_DOMAIN
    zim_manager_domain: str = DEFAULT_ZIM_MANAGER_DOMAIN

    # database
    db_path: Path = DEFAULT_DB_PATH
    jmx_path: Path = DEFAULT_JMX_PATH

    # e2e params
    ssid: str = DEFAULT_SSID
    passphrase: str = DEFAULT_PASSPHRASE
    max_devices: int = DEFAULT_MAX_DEVICES
    exclude_broadcom: bool = DEFAULT_EXCLUDE_BROADCOM
    exclude_ifnames: list[str] = field(default_factory=list[str])
    exclude_vendors: list[str] = field(default_factory=list[str])
    exclude_hwaddrs: list[str] = field(default_factory=list[str])
    address_network: IPv4Network = DEFAULT_ADDRESS_NETWORK
    ping_address: IPv4Address = DEFAULT_PING_ADDRESS
    gateway_address: IPv4Address = DEFAULT_GATEWAY_ADDRESS
    dns_address: IPv4Address = DEFAULT_DNS_ADDRESS
    dns_captured_address: IPv4Address = DEFAULT_DNS_CAPTURED_DOMAIN_IP
    assume_online: bool = DEFAULT_ASSUME_ONLINE
    content_id: str = DEFAULT_CONTENT_ID

    logger: logging.Logger = logging.getLogger(NAME)  # noqa: RUF009

    def __post_init__(self):
        broadcom_vendor = "Broadcom Corp."
        if self.exclude_broadcom and broadcom_vendor not in self.exclude_vendors:
            self.exclude_vendors.append(broadcom_vendor)
        self._db = SqliteExtDatabase(
            self.db_path,
            pragmas={
                "journal_mode": "wal",
                "cache_size": -1 * 64000,  # 64MB
                "foreign_keys": 1,
                "ignore_check_constraints": 0,
                "synchronous": 0,
            },
        )

    @property
    def fqdn(self) -> str:
        return ".".join((self.fld, self.tld))

    @property
    def db(self) -> SqliteExtDatabase:
        if not self._db:
            raise OSError("_db not set")
        return self._db

    @classmethod
    def setup(cls, **kwargs: Any):
        if cls._instance:
            raise OSError("Already inited Context")
        cls._instance = cls(**kwargs)
        cls.setup_logger()
        cls._instance.__post_init__()

    @classmethod
    def setup_logger(cls):
        debug = cls._instance.debug if cls._instance else cls.debug
        if cls._instance:
            cls._instance.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        else:
            cls.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(asctime)s %(levelname)s | %(message)s",
        )

    @classmethod
    def get(cls) -> "Context":
        if not cls._instance:
            raise OSError("Uninitialized context")  # pragma: no cover
        return cls._instance
