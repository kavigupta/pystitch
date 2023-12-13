import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--slow_test",
        action="store_true",
        help="run the tests only in case of that command line (marked with marker @slow_test)",
    )


def pytest_runtest_setup(item):
    if "slow_test" in item.keywords and not item.config.getoption("--slow_test"):
        pytest.skip("need --slow_test option to run this test")
