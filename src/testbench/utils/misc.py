from humanfriendly import format_size


def format_speed(size: int, duration: int | float, *, bps: bool = False) -> str:
    """5MB/s like formatting of speed from size (bytes) and duration (seconds)

    bps params allow a bits per second output (40mbps)"""

    try:
        bytes_per_seconds = size // int(duration)
    except ZeroDivisionError:
        bytes_per_seconds = 0
    if bps:
        return (
            format_size(bytes_per_seconds * 8)
            .lower()
            .replace("bytes", "b")
            .replace(" ", "")
            + "ps"
        )
    return f"{format_size(bytes_per_seconds)}/s"
