#!/usr/bin/env python

import argparse
import logging
import sys
from dataclasses import dataclass, field

from testbench.__about__ import __version__
from testbench.utils.wlan import get_wireless_devices

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("max-wlan")


@dataclass
class Options:
    ssid: str = "testbench"
    max_devices: int = 0
    excluded_ifname: list[str] = field(default_factory=list)
    passphrase: str | None = None
    address_network: str | None = None
    ping_address: str = "192.168.2.1"
    gateway_address: str = "192.168.2.1"
    http_addresses: list[str] = field(default_factory=list)
    debug: bool = False


def run_wlan_max(options: Options):
    logger.info(f"Starting with {options}…")

    ifnames = get_wireless_devices(excluding=options.excluded_ifname or [])
    logger.info(f"Found {len(ifnames)} wireless devices")
    for ifname in ifnames:
        logger.info(f"- {ifname}")


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="max-wlan",
        description="Test max nb of Wireless (IEEE802.11) devices can connect",
    )

    parser.add_argument(
        "--debug",
        help="Enable verbose output",
        action="store_true",
        default=Options.debug,
    )

    parser.add_argument(
        "--ssid",
        help="SSID of network to connect to (Offspot SSID)",
        dest="ssid",
        default=Options.ssid,
        required=False,
    )

    parser.add_argument(
        "--passphrase",
        help="WPA2 Passphrase of network to connect to",
        dest="passphrase",
        default="testbench",
        required=False,
    )

    parser.add_argument(
        "--max-devices",
        help="Max number of local devices to use (defaults to max available)",
        dest="max_devices",
        type=int,
        default=Options.max_devices,
        required=False,
    )

    parser.add_argument(
        "--exclude-ifname",
        help="Interface name to exclude from testing devices (wlan0 usually)",
        dest="excluded_ifname",
        action="append",
        required=False,
    )

    parser.add_argument(
        "--address-network",
        help="IPv4 network to ensure received address is inside (otherwise not tested)",
        dest="address_network",
        required=False,
    )

    parser.add_argument(
        "--ping-address",
        help="IPv4 address to ping (ICMP) once connected",
        dest="ping_address",
        default=Options.ping_address,
        required=False,
    )

    parser.add_argument(
        "--gateway-address",
        help="IPv4 address to make sure was received",
        dest="gateway_address",
        default=Options.gateway_address,
        required=False,
    )

    parser.add_argument(
        "--http-address",
        help="HTTP(s) address to query, expecting 200 OK",
        dest="http_addresses",
        action="append",
        default=["http://goto.kiwix.hotspot"],
        required=False,
    )

    parser.add_argument(
        "--version",
        help="Display version and exit",
        action="version",
        version=__version__,
    )

    args = parser.parse_args()

    try:
        options = Options(**dict(args._get_kwargs()))
        sys.exit(run_wlan_max(options))
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    entrypoint()
