import argparse
import sys
from pathlib import Path

from testbench.cli.randterm import KINDS as RANDTERM_KINDS
from testbench.cli.randterm import gen_suggestions
from testbench.cli.randterm import main as randterm_main
from testbench.context import Context

logger = Context.logger


def stream():
    parser = argparse.ArgumentParser(prog="stream")

    parser.add_argument("--ifname", help="iface to test via", dest="ifname")
    parser.add_argument(
        "--service-url",
        help="Kiwix serve URL",
        dest="service_url",
        default="http://browse.kiwix.hotspot",
    )
    parser.add_argument(
        "--content-id",
        help="ZIM ID for video",
        dest="content_id",
        default="mali-pour-les-nuls_fr_all",
    )
    parser.add_argument(
        "--play-duration",
        help=(
            "Stop after this duration (seconds) playing. "
            "If not set, stops once download is complete"
        ),
        type=int,
        default=0,
        dest="play_duration",
    )
    parser.add_argument(help="Video slug in ZIM", dest="video_slug")

    args = parser.parse_args(sys.argv[1:])
    # ignore unset values in order to not override Context defaults
    args_dict = {key: value for key, value in args._get_kwargs() if value}

    Context.setup(command="stream")

    from testbench.scripts.streamvideo import stream_video

    try:
        sys.exit(stream_video(**args_dict))
    except Exception as exc:
        logger.error(f"General failure: {exc!s}")
        logger.exception(exc)
    sys.exit(1)


def randterm():
    parser = argparse.ArgumentParser(prog="randterm")
    parser.add_argument(
        help="Which kind of term to get?", dest="kind", choices=RANDTERM_KINDS
    )

    args = parser.parse_args(sys.argv[1:])
    # ignore unset values in order to not override Context defaults
    args_dict = {key: value for key, value in args._get_kwargs() if value}

    try:
        sys.exit(randterm_main(**args_dict))
    except Exception as exc:
        logger.error(f"General failure: {exc!s}")
        logger.exception(exc)
    sys.exit(1)


def gensugg():
    parser = argparse.ArgumentParser(prog="gensugg")
    parser.add_argument(
        "--path", help="File to write suggestions to", dest="fpath", type=Path
    )
    parser.add_argument(
        "--len",
        help="Length (in characters) for the longest suggestions to gen",
        dest="max_len",
        type=int,
    )

    args = parser.parse_args(sys.argv[1:])
    # ignore unset values in order to not override Context defaults
    args_dict = {key: value for key, value in args._get_kwargs() if value}

    try:
        sys.exit(gen_suggestions(**args_dict))
    except Exception as exc:
        logger.error(f"General failure: {exc!s}")
        logger.exception(exc)
    sys.exit(1)
