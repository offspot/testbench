# pyright: strict, reportUnusedExpression=false

from testbench.__about__ import __version__


def test_version():
    assert "dev" in __version__
