import csv
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Callable

import attr
from humanfriendly import format_size, format_timespan, parse_size, parse_timespan

from contrib.common import get_ifnames
from testbench.utils.misc import StreamExitCodes, format_speed


def get_curl_downloadspeed(folder: Path, ifname: str) -> int:
    dlspeed_re = re.compile(r"^downloadspeed:\s(?P<value>\d+)\sbyte/sec$")
    fpath = folder.joinpath(f"curl-{ifname}.txt")
    lines = fpath.read_text().splitlines()
    for line in reversed(lines):
        if m := dlspeed_re.match(line.strip()):
            return int(m.groupdict()["value"])


# Video size: 13.57 MB
# Video duration: 14 minutes and 48 seconds
# Downloaded: 100% of 13.57 MB
# Average speed: 3.88mbps 13.57 MB in 28.71 seconds
# Played: 29 seconds
# Frozed for: 0 seconds


@attr.define
class StreamResult:
    ifname: str = ""
    filesize: int = -1
    video_duration: float = -1
    downloaded: int = -1
    duration: float = -1
    played: float = -1
    frozed: float = -1
    exit: int = -1


def read_stream(fpath: Path) -> StreamResult:
    lines = fpath.read_text().splitlines()

    mapping: dict[str, tuple[Callable[[Any], str | int | float], str]] = {
        "ifname": (str, r"^ifname='(?P<value>wlan[0-9]+)'$"),
        "filesize": (int, r"^Video size: (.+) \((?P<value>\d+)\)$"),
        "video_duration": (
            float,
            r"^Video duration: (.+) \((?P<value>[\d\.]+)\)$",
        ),
        "duration": (
            float,
            r"^Average speed: (.+) \((\d+) -- (?P<value>[\d\.]+)\)$",
        ),
        "played": (float, r"^Played: (.+) \((?P<value>[\d\.]+)\)"),
        "frozed": (float, r"^Frozed for: (.+) \((?P<value>[\d\.]+)\)"),
    }

    result = StreamResult()
    for line in lines[:6] + lines[-4:]:
        for varname, process in mapping.items():
            match = re.match(process[1], line)
            if match:
                setattr(result, varname, process[0](match.groupdict()["value"]))

    return result


def main(folder: Path) -> int:
    ifnames = get_ifnames(folder.joinpath("ifnames.csv"))

    def get_ifname_for(thname: str) -> str:
        num = int(thname.split(" ", 1)[-1].split("-", 1)[-1])
        return ifnames[num - 1]

    results: list[StreamResult] = []

    with open(folder.joinpath("results.csv")) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ifname = get_ifname_for(row["threadName"])
            stream = read_stream(folder.joinpath(f"stream-{ifname}.txt"))
            stream.exit = int(row["responseCode"])
            results.append(stream)

    filesize = results[0].filesize
    video_duration = results[0].video_duration
    print(f"Video size: {format_size(filesize)}")
    print(f"Video duration: {format_timespan(video_duration)}")
    durations = [res.duration for res in results]
    print(
        "Max speed",
        format_speed(filesize, min(durations)),
        f"({format_speed(filesize, min(durations), bps=True)})",
    )
    print(
        "Min speed",
        format_speed(filesize, max(durations)),
        f"({format_speed(filesize, max(durations), bps=True)})",
    )
    print(
        "Average speed",
        format_speed(filesize, statistics.mean(durations)),
        f"({format_speed(filesize, statistics.mean(durations), bps=True)})",
    )
    frozes = [res.frozed for res in results if res.frozed]
    if frozes:
        print("Min non-zero freeze", format_timespan(min(frozes)))
        print("Max non-zero freeze", format_timespan(max(frozes)))
        print("Avg non-zero freeze", format_timespan(statistics.mean(frozes)))

    for ec in StreamExitCodes.__members__.values():
        print(
            f"Nb `{ec.name}`:",
            len(list(filter(lambda sr: sr.exit == ec, results))),
        )
    return 0


if __name__ == "__main__":

    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f"Usage {sys.argv[0]} JMETER_OUTPUT_FOLDER")
        sys.exit(1)
    sys.exit(main(folder=Path(sys.argv[1])))
