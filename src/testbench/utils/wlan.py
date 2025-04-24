import fnmatch
import random
import re
import subprocess
from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path
from typing import NamedTuple, Self

from nmcli import device as nmdevice

# from nmcli.data.device import NMDevice

NM_CONN_DIR = Path("/etc/NetworkManager/system-connections/")
NMSHOW_FIELDS = [
    "GENERAL.DEVICE",
    "GENERAL.TYPE",
    "GENERAL.HWADDR",
    "GENERAL.MTU",
    "GENERAL.STATE",
    "GENERAL.CONNECTION",
    "GENERAL.CON-PATH",
    "IP4.ADDRESS",
    "IP4.GATEWAY",
    "IP4.DNS",
    # "IP6.GATEWAY",
    "GENERAL.VENDOR",
]
RE_NUMS_ALPHA = re.compile(r"(\d+)|(\D+)")
RE_ROUTE_NM = re.compile(
    r"dst = ?P<dst>(\d+\.\d+\.\d+\.\d+\/\d+), "  # noqa: ISC003
    + r"nh = ?P<nh>(\d+\.\d+\.\d+\.\d+\/\d+), mt = ?P<mt>(\d+)"
)


@dataclass(kw_only=True)
class IP4Route:
    destination: IPv4Address  #  192.168.2.0
    gateway: IPv4Address  # 0.0.0.0
    metric: int  # 636

    @classmethod
    def from_nmshow(cls, route: str) -> Self | None:
        # dst = 192.168.5.0/24, nh = 0.0.0.0, mt = 100
        if m := RE_ROUTE_NM.match(route):
            return cls(
                destination=IPv4Address(m.groupdict()["dst"].split("/", 1)[0]),
                gateway=IPv4Address(m.groupdict()["nh"].split("/", 1)[0]),
                metric=int(m.groupdict()["dst"]),
            )
        return None


@dataclass(kw_only=True)
class IP4Link:
    address: IPv4Address  # 192.168.2.169/24
    gateway: IPv4Address | None  # 192.168.2.1
    route: IP4Route | None
    dns: IPv4Address | None  # "192.168.2.1"

    @classmethod
    def from_nmshow(cls, payload: dict[str, str | None]) -> Self:
        return cls(
            address=IPv4Address(str(payload["IP4.ADDRESS[1]"]).split("/", 1)[0]),
            gateway=(
                IPv4Address(str(payload["IP4.GATEWAY"]).split("/", 1)[0])
                if payload.get("IP4.GATEWAY")
                else None
            ),
            route=(
                IP4Route.from_nmshow(str(payload["IP4.ROUTE[1]"]))
                if payload.get("IP4.ROUTE[1]")
                else None
            ),
            dns=(
                IPv4Address(str(payload["IP4.DNS[1]"]).split("/", 1)[0])
                if payload.get("IP4.DNS[1]")
                else None
            ),
        )


@dataclass(kw_only=True)
class WirelessDevice:
    ifname: str  # wlan1
    hwaddr: str  # 7C:C2:C6:1B:09:60
    mtu: int  # 1500
    state: str  # 100 (connected)
    connection: str | None  # testbench 1
    conpath: Path | None  # /org/freedesktop/NetworkManager/ActiveConnection/293
    ip4: IP4Link | None
    vendor: str

    @property
    def ip4link(self) -> IP4Link:
        if not self.ip4:
            raise OSError("No IPv4 Link")
        return self.ip4

    @classmethod
    def from_nmshow(cls, payload: dict[str, str | None]) -> Self:
        return cls(
            ifname=str(payload["GENERAL.DEVICE"]),
            hwaddr=str(payload["GENERAL.HWADDR"]).lower(),
            mtu=int(str(payload["GENERAL.MTU"])),
            state=str(payload["GENERAL.STATE"]),
            connection=payload.get("GENERAL.CONNECTION"),
            conpath=(
                Path(str(payload["GENERAL.CON-PATH"]))
                if payload.get("GENERAL.CON-PATH")
                else None
            ),
            ip4=IP4Link.from_nmshow(payload) if payload.get("IP4.ADDRESS[1]") else None,
            vendor=payload.get("GENERAL.VENDOR") or "",
        )

    def refresh(self):
        payload = nmdevice.show(self.ifname, fields=",".join(NMSHOW_FIELDS))
        self.hwaddr = str(payload["GENERAL.HWADDR"]).lower()
        self.mtu = int(str(payload["GENERAL.MTU"]))
        self.state = str(payload["GENERAL.STATE"])
        self.connection = payload.get("GENERAL.CONNECTION")
        self.conpath = (
            Path(str(payload["GENERAL.CON-PATH"]))
            if payload.get("GENERAL.CON-PATH")
            else None
        )
        self.ip4 = (
            IP4Link.from_nmshow(payload) if payload.get("IP4.ADDRESS[1]") else None
        )
        self.vendor = payload.get("GENERAL.VENDOR") or ""


def wirelessdevice_name_key(device: WirelessDevice) -> tuple[int | str, ...]:
    return tuple(
        int(num) if num else str(alpha)
        for num, alpha in RE_NUMS_ALPHA.findall(device.ifname)
    )


def get_wireless_devices(
    *,
    excluding_ifnames: list[str],
    excluding_vendors: list[str],
    excluding_hwaddrs: list[str],
    max_devices: int,
) -> dict[str, WirelessDevice]:

    def matches(entry: dict[str, str | None]) -> bool:
        conditions = [
            entry["GENERAL.TYPE"] == "wifi",
            # entry["GENERAL.DEVICE"] not in excluding_ifnames,
        ]
        if excluding_ifnames:
            for ifname in excluding_ifnames:
                conditions.append(
                    not fnmatch.fnmatch(str(entry["GENERAL.DEVICE"]), ifname.lower())
                )
        if excluding_vendors:
            for vendor in excluding_vendors:
                conditions.append(
                    # vendor.lower() not in (entry["GENERAL.VENDOR"] or "").lower()
                    not fnmatch.fnmatch(
                        (entry["GENERAL.VENDOR"] or "").lower(), vendor.lower()
                    )
                )
        if excluding_hwaddrs:
            for hwaddr in excluding_hwaddrs:
                conditions.append(
                    not fnmatch.fnmatch(
                        str(entry["GENERAL.HWADDR"]).lower(), hwaddr.lower()
                    )
                )
        return all(conditions)

    devices: list[WirelessDevice] = [
        WirelessDevice.from_nmshow(entry)
        for entry in nmdevice.show_all(  # pyright: ignore[reportUnknownMemberType]
            fields=",".join(NMSHOW_FIELDS)
        )
        if matches(entry)
    ]
    devices.sort(key=wirelessdevice_name_key)

    if max_devices:
        random.shuffle(devices)
        devices = devices[:max_devices]

    return {device.ifname: device for device in devices}


def get_some_wireless_devices(*, ifnames: list[str]) -> dict[str, WirelessDevice]:
    return {
        ifname: device
        for ifname, device in get_wireless_devices(
            excluding_ifnames=[],
            excluding_vendors=[],
            excluding_hwaddrs=[],
            max_devices=0,
        ).items()
        if ifname in ifnames
    }


class CompletedProcess(NamedTuple):
    args: list[str]
    returncode: int
    stdout: str

    @property
    def succeedeed(self):
        return self.returncode == 0


def run_command(args: list[str]) -> CompletedProcess:
    ps = subprocess.run(
        args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
    )
    return CompletedProcess(
        args=ps.args,
        returncode=ps.returncode,
        stdout=ps.stdout.strip() if ps.stdout else "",
    )


def connect_device(
    ifname: str,
    *,
    ssid: str,
    passphrase: str | None,
    rescan: bool = False,  # noqa: ARG001
) -> CompletedProcess:
    args = ["nmcli", "device", "wifi", "connect", ssid]
    if passphrase:
        args += ["password", str(passphrase)]
    args += ["ifname", ifname]
    return run_command(args)


def disconnect_device(device: WirelessDevice) -> CompletedProcess:
    if device.connection:
        run_command(["nmcli", "connection", "delete", "id", device.connection])
    return run_command(["nmcli", "device", "disconnect", device.ifname])


def disconnect_devices(devices: list[WirelessDevice]):
    for device in devices:
        disconnect_device(device)


def ping_host(ifname: str, host: str) -> tuple[bool, str]:
    ps = run_command(["ping", "-4", "-c", "4", "-I", ifname, host])
    last_line = ps.stdout.strip().splitlines()[-1] if ps.stdout else ""
    return ps.succeedeed, last_line


def reset_connections():
    devices = get_wireless_devices(
        excluding_ifnames=[], excluding_vendors=[], excluding_hwaddrs=[], max_devices=0
    )
    disconnect_devices(devices=list(devices.values()))
    for fpath in NM_CONN_DIR.glob("*.nmconnection"):
        fpath.unlink(missing_ok=True)
