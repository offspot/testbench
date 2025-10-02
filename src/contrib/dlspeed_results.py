import csv
import re
import statistics
import sys
from pathlib import Path

from humanfriendly import format_size, format_timespan

from testbench.utils.misc import format_speed


def get_ifnames(fpath: Path) -> list[str]:
    with open(fpath) as fh:
        reader = csv.DictReader(fh)
        return [row["ifname"] for row in reader]
    return []


def get_download_size_from_results(fpath: Path) -> int:
    """extract download file size in bytes from results.csv"""
    with open(fpath) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("success") == "true" and row.get("bytes"):
                size = int(row["bytes"])
                if size:
                    return size
    return 0


def get_download_size_from_curl(folder: Path, ifnames: list[str]) -> int:
    size_re = re.compile(r"^size:\s(?P<value>\d+)\sbytes$")
    exitcode_re = re.compile(r"^exitcode:\s(?P<code>\d+)\s*$")
    succeeded = False
    for ifname in ifnames:
        lines = folder.joinpath(f"curl-{ifname}.txt").read_text().splitlines()
        for line in reversed(lines):
            if m := exitcode_re.match(line.strip()):
                succeeded = m.groupdict()["code"] == "0"
                if not succeeded:
                    break
            if m := size_re.match(line.strip()):
                size = int(m.groupdict()["value"])
                if size:
                    return size
    return 0


def get_curl_downloadspeed(folder: Path, ifname: str) -> int:
    dlspeed_re = re.compile(r"^downloadspeed:\s(?P<value>\d+)\sbyte/sec$")
    fpath = folder.joinpath(f"curl-{ifname}.txt")
    lines = fpath.read_text().splitlines()
    for line in reversed(lines):
        if m := dlspeed_re.match(line.strip()):
            return int(m.groupdict()["value"])
    return -1


def main(folder: Path) -> int:
    ifnames = get_ifnames(folder.joinpath("ifnames.csv"))
    download_size = get_download_size_from_results(
        folder.joinpath("results.csv")
    ) or get_download_size_from_curl(folder=folder, ifnames=ifnames)
    if not download_size:
        raise OSError(f"Unable to compute {download_size=}")

    def get_ifname_for(thname: str) -> str:
        num = int(thname.split(" ", 1)[-1].split("-", 1)[-1])
        return ifnames[num - 1]

    failure_ifnames: list[str] = []
    durations: list[float] = []

    # get download
    with open(folder.joinpath("results.csv")) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ifname = get_ifname_for(row["threadName"])
            if not row.get("success") == "true":
                failure_ifnames.append(ifname)
                continue
            duration = int(row["elapsed"]) / 1000
            print(f"> {ifname}, {duration}, {format_speed(download_size, duration)}")
            durations.append(duration)

    print(f"Download size, {download_size}, {format_size(download_size)}")
    print(f"Nb. ifaces, {len(ifnames)}")
    print(f"Nb success, {len(ifnames)}")
    print(
        f"Average speed: {format_speed(download_size, statistics.mean(durations))} "
        f"({format_speed(download_size, statistics.mean(durations), bps=True)})"
        f", {format_timespan(statistics.mean(durations))}"
    )
    print(
        f"Max speed: {format_speed(download_size, min(durations))} "
        f"({format_speed(download_size, min(durations), bps=True)})"
        f", {format_timespan(min(durations))}"
    )
    print(
        f"Min speed: {format_speed(download_size, max(durations))} "
        f"({format_speed(download_size, max(durations), bps=True)})"
        f", {format_timespan(max(durations))}"
    )
    if not failure_ifnames:
        comb_size = download_size * len(ifnames)
        print(
            f"Combined~ throughput: "
            f"{format_speed(comb_size, statistics.mean(durations))} "
            f"({format_speed(comb_size, statistics.mean(durations), bps=True)})"
        )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f"Usage {sys.argv[0]} JMETER_OUTPUT_FOLDER")
        sys.exit(1)
    sys.exit(main(folder=Path(sys.argv[1])))
