import argparse
import signal
import sys
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import FrameType

from testbench.__about__ import __version__
from testbench.context import DEFAULT_DB_PATH, NAME_CLI, Context

logger = Context.logger


def prepare_context(raw_args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog=NAME_CLI,
        description="Kiwix Hotstpot testbench toolbox",
        epilog="https://github.com/offspot/testbench",
    )

    parser.add_argument(
        "--debug",
        help="Enable verbose output",
        action="store_true",
        default=Context.debug,
    )

    parser.add_argument(
        "--db",
        help="Path to SQLite database",
        type=Path,
        default=DEFAULT_DB_PATH,
        dest="db_path",
    )

    parser.add_argument(
        "--version",
        help="Display version and exit",
        action="version",
        version=__version__,
    )

    parser.add_argument(
        "--exclude-broadcom",
        help="Exclude Broadcom WiFi devices (vendor of integrated chipset in Pi)",
        action="store_true",
        dest="exclude_broadcom",
        default=Context.exclude_broadcom,
    )

    parser.add_argument(
        "--exclude-ifname",
        help="Interface name to exclude from testing devices (matching)",
        dest="exclude_ifnames",
        action="append",
        required=False,
    )

    parser.add_argument(
        "--exclude-vendor",
        help="Interface to exclude from testing via its Vendor name (ex; Realtek)",
        dest="exclude_vendors",
        action="append",
        required=False,
    )

    parser.add_argument(
        "--exclude-hwaddr",
        help="Interface to exclude from testing via its MAC Address name (matching)",
        dest="exclude_hwaddrs",
        action="append",
        required=False,
    )

    parser.add_argument(
        "--max-devices",
        help="Max number of local devices to use (defaults to max available)",
        dest="max_devices",
        type=int,
        default=Context.max_devices,
        required=False,
    )

    subparsers = parser.add_subparsers(
        help="Available subcommands", required=True, dest="command"
    )

    # status_parser
    subparsers.add_parser(
        "status",
        help="Query the testbench host for its status "
        "(number of available WiFi devices, mostly)",
    )

    integration_parser = subparsers.add_parser(
        "integration", help="Integration/capacity tests"
    )

    integration_parser.add_argument(
        "--ssid",
        help="SSID of network to connect to (Offspot SSID)",
        dest="ssid",
        default=Context.ssid,
        required=False,
    )

    integration_parser.add_argument(
        "--passphrase",
        help="WPA2 Passphrase of network to connect to",
        dest="passphrase",
        default=Context.passphrase,
        required=False,
    )

    integration_parser.add_argument(
        "--address-network",
        help="IPv4 network to ensure received address is inside (otherwise not tested)",
        dest="address_network",
        type=IPv4Network,
        default=Context.address_network,
        required=False,
    )

    integration_parser.add_argument(
        "--ping-address",
        help="IPv4 address to ping (ICMP) once connected",
        dest="ping_address",
        type=IPv4Address,
        default=Context.ping_address,
        required=False,
    )

    integration_parser.add_argument(
        "--gateway-address",
        help="IPv4 address to make sure was received",
        dest="gateway_address",
        type=IPv4Address,
        default=Context.gateway_address,
        required=False,
    )

    integration_parser.add_argument(
        "--assume-online",
        help="Whether target device is assumed to be online or not",
        action="store_true",
        dest="assume_online",
        default=Context.assume_online,
        required=False,
    )

    perf_parser = subparsers.add_parser(
        "perf",
        help="Query the testbench host for its status "
        "(number of available WiFi devices, mostly)",
    )

    perf_parser.add_argument(
        "--jmx", help="Path to own JMX file", type=Path, default=None, dest="jmx_path"
    )

    perf_parser.add_argument(
        "--assume-online",
        help="Whether target device is assumed to be online or not",
        action="store_true",
        dest="assume_online",
        default=Context.assume_online,
        required=False,
    )

    perf_parser.add_argument(
        "--content-id",
        help="Hotspot ident of ZIM content to query",
        dest="content_id",
        default=Context.content_id,
        required=False,
    )

    args = parser.parse_args(raw_args)
    # ignore unset values in order to not override Context defaults
    args_dict = {key: value for key, value in args._get_kwargs() if value}

    Context.setup(**args_dict)


def main() -> int:
    debug = Context.debug
    try:
        prepare_context(sys.argv[1:])
        context = Context.get()
        debug = context.debug

        # late import as to have an initialized Context
        match context.command:
            case "status":

                from testbench.cli.status import main as main_prog

            case "integration":
                from testbench.cli.integration import main as main_prog

            case "perf":
                from testbench.cli.perf import main as main_prog
            case _:
                return 1

        def exit_gracefully(signum: int, frame: FrameType | None):  # noqa: ARG001
            print("\n", flush=True)
            logger.info(f"Received {signal.Signals(signum).name}/{signum}. Exiting")
            # stop?

        signal.signal(signal.SIGTERM, exit_gracefully)
        signal.signal(signal.SIGINT, exit_gracefully)
        signal.signal(signal.SIGQUIT, exit_gracefully)

        return main_prog()
    except Exception as exc:
        logger.error(f"General failure: {exc!s}")
        if debug:
            logger.exception(exc)
        return 1


def entrypoint():
    sys.exit(main())
