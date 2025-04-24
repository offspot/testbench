import click

from testbench.context import Context
from testbench.hardware import WirelessDevicesList, get_all_wireless_devices

context = Context.get()


def greet_for(name: str):
    click.echo(click.style(name.upper(), fg="blue"))


def get_filtered_wireless_devices() -> WirelessDevicesList:
    all_wireless_devices = get_all_wireless_devices(
        excluding_broadcom=context.exclude_broadcom,
        excluding_ifnames=context.exclude_ifnames,
        excluding_vendors=context.exclude_vendors,
        excluding_hwaddrs=context.exclude_hwaddrs,
        max_devices=context.max_devices,
    )
    click.echo(f"- excluding_broadcom: {context.exclude_broadcom}")
    click.echo(f"- excluding_ifnames: {context.exclude_ifnames}")
    click.echo(f"- excluding_vendors: {context.exclude_vendors}")
    click.echo(f"- excluding_hwaddrs: {context.exclude_hwaddrs}")
    click.echo(f"- max_devices: {context.max_devices}")
    click.echo(
        click.style(
            f"> Configured for {all_wireless_devices.count} devices", fg="green"
        )
    )
    return all_wireless_devices
