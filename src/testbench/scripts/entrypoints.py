import argparse
import sys

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
