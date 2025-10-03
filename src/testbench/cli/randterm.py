import itertools
import json
import random
import string
from pathlib import Path

DATA_FOLDER = Path(__file__).parent.parent.parent.joinpath("data")
SUGGESTIONS_TERM_PATH = DATA_FOLDER.joinpath("suggestions.txt")
# https://github.com/dwyl/english-words
SEARCH_TERM_PATH = DATA_FOLDER.joinpath("words.txt")
KINDS = ("suggestion", "search")


def gen_suggestions(fpath: Path = SUGGESTIONS_TERM_PATH, max_len: int = 4) -> int:
    with open(fpath, "w") as fh:
        for length in range(0, max_len + 1):
            for combination in itertools.combinations_with_replacement(
                string.ascii_letters, length
            ):
                value = "".join(combination)
                if value:
                    fh.write(f"{value}\n")
    return 0


def get_term(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"Unsupprted kind: {kind}")
    if not SUGGESTIONS_TERM_PATH.exists():
        gen_suggestions(fpath=SUGGESTIONS_TERM_PATH)

    fpath = SUGGESTIONS_TERM_PATH if kind == "suggestion" else SEARCH_TERM_PATH

    with open(fpath, "rb") as fh:
        nb_lines = sum(1 for _ in fh)
    line_num = random.randint(0, nb_lines)  # noqa: S311

    with open(fpath) as fh:
        for _ in range(0, line_num):
            fh.readline()
        return fh.readline().strip()


def main(kind: str) -> int:
    print(json.dumps({"term": get_term(kind)}, indent=4))
    return 0
