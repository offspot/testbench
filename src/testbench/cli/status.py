import click
from prettytable import PrettyTable

from testbench.cli.common import get_filtered_wireless_devices, greet_for
from testbench.context import Context
from testbench.utils.wlan import reset_connections

context = Context.get()
logger = context.logger


def main() -> int:

    greet_for("WiFi Status")

    all_wireless_devices = get_filtered_wireless_devices()

    table = PrettyTable(field_names=["Ifname", "Vendor", "HW Addr"], align="l")
    for device in all_wireless_devices.devices:
        table.add_row([device.ifname, device.vendor, device.hwaddr])
    click.echo(table.get_string())  # pyright: ignore[reportUnknownMemberType]

    logger.debug("Disconnecting all devices…")
    reset_connections()

    return 0
