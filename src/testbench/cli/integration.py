from ipaddress import IPv4Network

import click
from halo import Halo  # pyright: ignore [reportMissingTypeStubs]
from humanfriendly import format_timespan
from prettytable import PrettyTable

from testbench.cli.common import get_filtered_wireless_devices, greet_for
from testbench.context import Context
from testbench.integration import (
    IntegrationTestsRunner,
    get_tests_collection,
)
from testbench.utils.wlan import (
    get_some_wireless_devices,
    reset_connections,
)

context = Context.get()
logger = context.logger


def main() -> int:
    greet_for("Integration Tests")

    all_wireless_devices = get_filtered_wireless_devices()
    devices = list(
        get_some_wireless_devices(
            ifnames=[dev.ifname for dev in all_wireless_devices.devices]
        ).values()
    )

    runner = IntegrationTestsRunner(
        devices=devices,
        collection=get_tests_collection(assume_online=context.assume_online),
        params={
            "ssid": context.ssid,
            "passphrase": context.passphrase,
            "dhcp_timeout": context.dhcp_timeout,
            "address_network": context.address_network,
            "gateway_address": context.gateway_address,
            "dns_address": context.dns_address,
            "ping_address": context.ping_address,
            "fqdn": context.fqdn,
            "fqdn_answer": str(context.gateway_address),
            "svc_fqdn": ".".join([context.svc_domain, context.fqdn]),
            "svc_fqdn_answer": str(context.gateway_address),
            "external_fqdn": "apple.com",
            "external_fqdn_answer": str(context.dns_captured_address),
            # when online
            "external_fqdn_answer_network": IPv4Network("17.0.0.0/8"),
            "zim_manager_fqdn": ".".join([context.zim_manager_domain, context.fqdn]),
        },
    )

    with click.progressbar(
        length=runner.nb_tests,
        show_eta=False,
        label=f"Running {runner.nb_test_per_device} tests "
        f"over {runner.nb_devices} devices",
    ) as bar:

        def update(last: int) -> int:
            new = runner.nb_completed_tests
            bar.update(n_steps=new - last)
            return new

        last = runner.nb_completed_tests
        runner.start()

        while runner.running:
            runner.tick(0.1)
            last = update(last)
        runner.shutdown(wait=True)
        update(last)

    click.echo(f"Tests completed in {format_timespan(runner.duration)}.")

    with Halo(text="Disconnecting all devices", spinner="dots") as spinner:
        reset_connections()
        spinner.succeed(  # pyright: ignore[reportUnknownMemberType]
            "Disconnected all devices"
        )

    if runner.all_succeeded:
        click.echo(click.style("All tests passed! 🎉", fg="green"))
    else:
        click.echo(
            click.style(
                f"[{runner.nb_sucessful_tests}/{runner.nb_tests}] tests passed",
                fg="yellow",
            )
        )

    tests_names = list(runner.results[devices[0].ifname].keys())
    table = PrettyTable(field_names=["Test"])
    table.align["Test"] = "l"
    for test_name in tests_names:
        table.add_row([test_name])
    for ifname, device_data in runner.results.items():
        results: list[str] = []
        for test_name in tests_names:
            result = device_data[test_name]
            results.append("✅" if result.succeeded else f"❌ {result.feedback}")
        table.add_column(
            ifname.replace("wlan", "wl"),
            results,
        )

    click.echo(table.get_string())  # pyright: ignore [reportUnknownMemberType]

    return 0
