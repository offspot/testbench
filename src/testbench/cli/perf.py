import csv
import re
import time
from dataclasses import dataclass

import click
from halo import Halo  # pyright: ignore [reportMissingTypeStubs]
from humanfriendly import format_number, format_timespan
from prettytable import PrettyTable

from testbench.cli.common import get_filtered_wireless_devices, greet_for
from testbench.context import Context
from testbench.jmeter import JMeterRunner
from testbench.utils.wlan import connect_device, reset_connections

context = Context.get()
logger = context.logger


@dataclass
class Result:
    nb_success: int
    nb_failed: int

    @property
    def nb_total(self) -> int:
        return self.nb_success + self.nb_failed

    @property
    def success_pc(self) -> float:
        return self.nb_success / self.nb_total

    @property
    def percent(self) -> str:
        return f"{format_number(self.success_pc * 100, 2)}%"


def main() -> int:

    greet_for("Performance Testing")

    if not context.jmx_path.resolve().exists():
        click.echo(
            click.style(f"JMX path does not exists: {context.jmx_path}", fg="red")
        )
        return 2

    all_wireless_devices = get_filtered_wireless_devices()

    with Halo(
        text=f"Connecting {all_wireless_devices.count} devices", spinner="dots"
    ) as spinner:
        for device in all_wireless_devices.devices:
            logger.debug(f"Connecting {device.ifname}")
            assert (  # noqa: S101
                connect_device(
                    device.ifname, ssid=context.ssid, passphrase=context.passphrase
                ).returncode
                == 0
            )
        spinner.succeed(  # pyright: ignore[reportUnknownMemberType]
            f"Connected {all_wireless_devices.count} devices"
        )

    with Halo(text="Starting JMeter", spinner="dots") as spinner:

        jmeter = JMeterRunner(
            context.jmx_path.resolve(),
            ifnames=[device.ifname for device in all_wireless_devices.devices],
            assume_online="true" if context.assume_online else "false",
            content_id=context.content_id,
        )
        jmeter.start()
        spinner.succeed(  # pyright: ignore[reportUnknownMemberType]
            f"Started JMeter, PID: {jmeter.ps.pid}"
        )

    with Halo(text="Running JMeter", spinner="dots") as spinner:
        while jmeter.is_running:
            time.sleep(1)
        if jmeter.succeeded:
            spinner.succeed(  # pyright: ignore[reportUnknownMemberType]
                f"JMeter completed in {format_timespan(jmeter.duration)}."
            )
        else:
            spinner.fail(  # pyright: ignore[reportUnknownMemberType]
                f"JMeter failed with {jmeter.ps.returncode} "
                f"after {format_timespan(jmeter.duration)}."
            )

    click.echo("")
    with Halo(text="Disconnecting all devices", spinner="dots") as spinner:
        reset_connections()
        spinner.succeed(  # pyright: ignore[reportUnknownMemberType]
            "Disconnected all devices"
        )

    if not jmeter.succeeded:
        return jmeter.ps.returncode

    click.echo(f"Results in {jmeter.results_csv_path}")

    def get_ifname_from_threadname(name: str) -> str:
        m = re.match(r"Users 1-(?P<num>\d+){1,2}", name)
        if m:
            return all_wireless_devices.devices[int(m.groupdict()["num"]) - 1].ifname
        raise ValueError(f"Inrecognized thread name: {name}")

    tests_map: dict[str, Result] = {}
    ifnames_map: dict[str, Result] = {}

    with open(jmeter.results_csv_path) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            label = row["label"]
            ifname = get_ifname_from_threadname(row["threadName"])
            success = row["success"] == "true"
            if label not in tests_map:
                tests_map[label] = Result(0, 0)
            tests_map[label].nb_success += 1 if success else 0
            tests_map[label].nb_failed += 1 if not success else 0
            if ifname not in ifnames_map:
                ifnames_map[ifname] = Result(0, 0)
            ifnames_map[ifname].nb_success += 1 if success else 0
            ifnames_map[ifname].nb_failed += 1 if not success else 0

    click.echo("")
    click.echo("Results by Test")

    tests_table = PrettyTable(
        field_names=["Test", "Success", "Failure", "Success rate"]
    )
    tests_table.align["Test"] = "l"
    for label, results in tests_map.items():
        tests_table.add_row(
            [label, results.nb_success, results.nb_failed, results.percent]
        )
    click.echo(tests_table.get_string())  # pyright: ignore [reportUnknownMemberType]

    click.echo("")
    click.echo("Results by Iface")

    ifnames_table = PrettyTable(
        field_names=["Iface", "Success", "Failure", "Success rate"]
    )
    for ifname, results in ifnames_map.items():
        ifnames_table.add_row(
            [ifname, results.nb_success, results.nb_failed, results.percent]
        )
    click.echo(ifnames_table.get_string())  # pyright: ignore [reportUnknownMemberType]

    return 0
