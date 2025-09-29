import datetime
import json
import subprocess
import time
from http import HTTPStatus
from threading import Lock, Thread
from typing import NamedTuple, Self

import attrs
from humanfriendly import format_number, format_size, format_timespan
from urllib3.poolmanager import PoolManager
from urllib3.response import BaseHTTPResponse

from testbench.context import Context
from testbench.utils.http import DEFAULT_TIMEOUT, get_session_for
from testbench.utils.misc import StreamExitCodes, format_speed
from testbench.utils.wlan import WirelessDevice

context = Context.get()
logger = context.logger


def get_video_duration(data: bytes) -> float:
    """video duration (seconds) from video file bytes (256K is safe)"""
    try:
        ps = subprocess.run(
            [
                "/usr/bin/env",
                "ffprobe",
                "-show_entries",
                "format=duration",
                "-output_format",
                "json",
                "-i",
                "-",
            ],
            check=False,
            capture_output=True,
            text=False,
            input=data,
        )
        if ps.returncode != 0:
            return 0
        return float(json.loads(ps.stdout)["format"]["duration"])
    except Exception as exc:
        logger.exception(exc)
    return 0


def get_now() -> datetime.datetime:
    """current datetime"""
    return datetime.datetime.now(tz=datetime.UTC)


class DataResult(NamedTuple):
    req_range: range
    resp_length: int = -1
    resp_range: range = range(-1, -1)
    received_length: int = -1
    code: HTTPStatus | None = None
    exception: Exception | None = None
    duration: float = 0
    retried: int = 0
    data: bytes = b""

    @property
    def succeeded(self) -> bool:
        return (
            self.exception is None
            and self.code is not None
            and 200 <= self.code <= 299  # noqa: PLR2004
        )

    @property
    def http_status(self) -> HTTPStatus:
        if self.code is None:
            raise OSError("no HTTP status code")
        return self.code


def get_data(
    session: PoolManager,
    url: str,
    start: int,
    end: int,
    *,
    drop_data: bool = True,
    attempts: int = 3,
) -> DataResult:
    """retry-friendly video chunk retrieval via chunked range requests"""

    retried = 0
    resp: BaseHTTPResponse = None  # pyright: ignore [reportAssignmentType]
    started_on = ended_on = get_now()
    while attempts:
        attempts -= 1
        try:
            resp = session.request(
                "GET",
                url=url,
                timeout=DEFAULT_TIMEOUT,
                redirect=False,
                headers={"Range": f"bytes={start!s}-{end!s}"},
            )
            ended_on = get_now()
        except Exception as exc:
            ended_on = get_now()
            retried += 1
            logger.exception(exc)

            if attempts:
                continue
            return DataResult(
                req_range=range(start, end), exception=exc, retried=retried
            )
        else:
            break

    try:
        content_range = resp.headers.get("Content-Range", "").split("bytes ", 1)[-1]
        received_range, received_totalsize = content_range.split("/", 1)
        resp_range = range(*[int(part) for part in received_range.split("-", 1)])
        resp_length = int(received_totalsize)
    except Exception:
        resp_range = range(-1, -1)
        resp_length = -1

    return DataResult(
        req_range=range(start, end),
        resp_length=resp_length,
        resp_range=resp_range,
        received_length=len(resp.data),
        code=HTTPStatus(resp.status),
        duration=(ended_on - started_on).total_seconds(),
        retried=retried,
        data=b"" if drop_data else resp.data,
    )


def parse_jsduration(text: str) -> float:
    """duration (seconds) from a Javascript Duration string

    doesnt support + and - signs

    assert parse_jsduration("PT20.345S") == 20.345
    assert parse_jsduration("PT15M") == 900
    assert parse_jsduration("PT10H") == 36000
    assert parse_jsduration("P2D") == 172800
    assert parse_jsduration("P2DT3H4M") == 183840
    assert parse_jsduration("PT1H4M") == 3840

    """
    # we only intend to support simple syntax so no signs
    text = text.upper().replace("-", "").replace("+", "")
    if not text.startswith("P"):
        raise ValueError("Malformed: not starting with P")
    suffixes = ["D", "H", "M", "S"]
    data: dict[str, float] = dict.fromkeys(suffixes, 0.0)
    suffix: str = ""
    value: str = ""
    seen_t = False
    for char in text[1:]:  # skipping P
        if char == "T":
            if value or (suffix and suffixes.index(suffix) >= suffixes.index("H")):
                raise ValueError(f"Malformed: T in {text.index('T')} position")
            suffix = ""
            seen_t = True
            continue
        if char in suffixes:
            if suffix and suffixes.index(suffix) >= suffixes.index(char):
                raise ValueError(f"Malformed ({char} after {suffix})")
            elif suffix and not value:
                raise ValueError(f"Malformed: {suffix} without value")
            if not seen_t and char != "D":
                raise ValueError("Malformed: no T before time")
            suffix = char
            data[suffix] = float(value)
            value = ""
            continue
        if not char.isdigit() and char != ".":
            raise ValueError(f"Malformed: invalid char {char}")
        value += char

    return (
        data.get("S", 0)
        + (data.get("M", 0) * 60)
        + (data.get("H", 0) * 3600)
        + (data.get("D", 0) * 86400)
    )


def format_percent(value: int, nb_rows: int) -> str:
    return f"{format_number(value * 100 / nb_rows, 2)}%"


@attrs.define
class VideoRequestInfo:
    ifname: str
    device: WirelessDevice
    session: PoolManager
    service_url: str
    content_id: str
    video_slug: str
    video_id: str
    video_duration: float
    video_path: str
    video_filesize: int

    @property
    def zim_url(self) -> str:
        return f"{self.service_url}/content/{self.content_id}"

    @property
    def bitrate(self) -> int:
        return int(self.video_filesize / self.video_duration)

    def get_bufsize(self, nb_seconds: int) -> int:
        return self.bitrate * nb_seconds

    @classmethod
    def from_slug(
        cls, ifname: str, service_url: str, content_id: str, video_slug: str
    ) -> Self:

        device = WirelessDevice.from_ifname(ifname)
        session = get_session_for(device=device, dns_server=context.dns_address)
        zim_url = f"{service_url}/content/{content_id}"
        resp = session.request(
            "GET", url=f"{zim_url}/videos/{video_slug}.json", timeout=DEFAULT_TIMEOUT
        )
        payload = resp.json()
        resp = session.request(
            "HEAD", url=f"{zim_url}/{payload['videoPath']}", timeout=DEFAULT_TIMEOUT
        )
        filesize = int(resp.headers.get("Content-Length", "-1"))
        return cls(
            ifname=ifname,
            device=device,
            session=session,
            service_url=service_url,
            content_id=content_id,
            video_slug=video_slug,
            video_id=payload["id"],
            video_duration=parse_jsduration(payload["duration"]),
            video_path=payload["videoPath"],
            video_filesize=filesize,
        )


class VideoPlayer:

    def __init__(self, filesize: int, duration: float):
        self.filesize = filesize
        self.duration = duration

        self.played_duration: float = 0
        self.frozen_duration: float = 0
        self.started_on: datetime.datetime = (
            None  # pyright: ignore [reportAttributeAccessIssue]
        )

        self.received_data = 0
        self.available_data = 0

        self.available_seconds: float = 0

        self.is_frozen = False

        self.play_thread = Thread(target=self.play_in_bg)

        self.download_started_on: datetime.datetime = (
            None  # pyright: ignore [reportAttributeAccessIssue]
        )
        self.download_completed_on: datetime.datetime = (
            None  # pyright: ignore [reportAttributeAccessIssue]
        )

        self.lock = Lock()

    @property
    def bitrate(self) -> int:
        return int(self.filesize / self.duration)

    def download(self, size: int):
        if not self.download_started_on:
            self.download_started_on = get_now()
        self.received_data += size
        with self.lock:
            self.available_data += size
            self.available_seconds += size / self.bitrate

        if self.missing_data <= 0:
            self.download_completed_on = get_now()

    @property
    def download_duration(self) -> float:
        if self.download_completed_on:
            return (
                self.download_completed_on - self.download_started_on
            ).total_seconds()
        return (get_now() - self.download_started_on).total_seconds()

    @property
    def consumed_data(self) -> int:
        return int(self.duration - self.remaining_time) * self.bitrate

    @property
    def missing_data(self) -> int:
        return self.filesize - self.received_data

    @property
    def available_buffer(self) -> int:
        return self.received_data - self.consumed_data

    @property
    def remaining_time(self) -> float:
        return self.duration - self.played_duration

    def play(self):
        self.started_on = self.checked_in = get_now()
        self.running = True
        self.play_thread.start()

    def play_in_bg(self):
        # duration of our iterations (sleep time here)
        iter_duration = 1
        iter_len = iter_duration * self.bitrate

        # stop if we dowloaded everything (we dont care about actual playing)
        # or requested to stop
        # or ended up finishing playing (shouldnt happend)
        while self.missing_data and self.running:
            if not self.available_data:
                self.frozen_duration += iter_duration
            else:
                with self.lock:
                    self.available_data -= iter_len
                    self.played_duration += iter_duration

            time.sleep(iter_duration)

    def stop(self):
        self.running = False
        self.play_thread.join(2)

    def print_status(self):
        print(
            f"Downloaded: {format_percent(self.received_data, self.filesize)} "
            f"of {format_size(self.filesize)}"
        )

        print(
            f"Average speed: "
            f"{format_speed(self.received_data, self.download_duration, bps=True)} "
            f"{format_size(self.received_data)} in "
            f"{format_timespan(self.download_duration)} "
            f"({self.received_data} -- {self.download_duration})"
        )
        print(
            f"Played: {format_timespan(self.played_duration)} "
            f"({self.played_duration})"
        )
        print(
            f"Frozed for: {format_timespan(self.frozen_duration)} "
            f"({self.frozen_duration})"
        )

    @property
    def completed(self) -> bool:
        return self.received_data >= self.filesize

    @property
    def done(self) -> bool:
        return self.remaining_time == 0


def stream_video(
    *,
    ifname: str,
    service_url: str,
    content_id: str,
    video_slug: str,
) -> int:

    print(f"{ifname=}")
    print(f"{service_url=}")
    print(f"{content_id=}")
    print(f"{video_slug=}")

    reqinfo = VideoRequestInfo.from_slug(
        ifname=ifname,
        service_url=service_url,
        content_id=content_id,
        video_slug=video_slug,
    )

    initial_bufsize = reqinfo.get_bufsize(10)  # get the first 10s before playing
    bufsize = reqinfo.get_bufsize(2)  # query 2s worth of video for every trip
    data: bytes

    player = VideoPlayer(
        filesize=reqinfo.video_filesize, duration=reqinfo.video_duration
    )
    player.download(0)  # set download start time

    try:
        resp = reqinfo.session.request(
            "GET",
            url=f"{reqinfo.zim_url}/{reqinfo.video_path}",
            timeout=DEFAULT_TIMEOUT,
            preload_content=False,
        )
        if resp.status not in (HTTPStatus.OK, HTTPStatus.PARTIAL_CONTENT):
            raise OSError(f"Unexpected HTTP code: {resp.status}: {resp.reason}")
    except Exception as exc:
        print(f"request exception: {exc}")
        logger.exception(exc)
        return 1

    print(
        f"Video size: {format_size(reqinfo.video_filesize)} "
        f"({reqinfo.video_filesize})"
    )
    print(
        f"Video duration: {format_timespan(reqinfo.video_duration)} "
        f"({reqinfo.video_duration})"
    )
    print("Content-Length", resp.headers.get("Content-Length"))
    print(f"initial buffer: {initial_bufsize}")
    print(f"regular buffer: {bufsize}")
    canceled = False

    try:
        data = resp._raw_read(amt=initial_bufsize)
    except Exception as exc:
        canceled = True
        logger.error(f"Failed to read data: {exc}")
        logger.exception(exc)
        return StreamExitCodes.NETWORK_ERROR

    while data and not canceled:

        try:
            player.download(len(data))
            if not player.started_on:
                player.play()
            player.print_status()

            data = resp._raw_read(amt=bufsize)
        except Exception as exc:
            canceled = True
            logger.error(f"Failed to read data: {exc}")
            logger.exception(exc)
            player.stop()

    player.stop()
    player.print_status()

    if canceled:
        return StreamExitCodes.NETWORK_ERROR

    if player.frozen_duration == 0:
        return 0

    if player.frozen_duration > (player.played_duration * 0.1):
        return StreamExitCodes.MAJOR_FREEZE
    elif player.frozen_duration:
        return StreamExitCodes.MINOR_FREEZE

    return StreamExitCodes.OK
