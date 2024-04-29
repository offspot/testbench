import re
from pathlib import Path

RE_NUMS_ALPHA = re.compile(r"(\d+)|(\D+)")


def natural_sortkey(string: str) -> tuple[int | str, ...]:
    return tuple(
        int(num) if num else str(alpha) for num, alpha in RE_NUMS_ALPHA.findall(string)
    )


def get_wireless_devices(excluding: list[str]):
    ifnames: list[str] = []
    for ifpath in Path("/sys/class/net/").glob("wl*"):
        if ifpath.name in excluding:
            continue
        ifnames.append(ifpath.name)
    return ifnames
