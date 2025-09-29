import csv
from pathlib import Path


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
