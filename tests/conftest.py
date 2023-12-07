import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_home_env_var():
    """Ensure that HOME is set.

    If HOME is missing from the environment or empty, it will be set to
    the current directory.
    """
    old_home_unset = "HOME" not in os.environ
    old_home = os.environ.get("HOME")

    if not old_home:
        os.environ["HOME"] = os.getcwd()

    yield

    if old_home_unset:
        del os.environ["HOME"]
    else:
        os.environ["HOME"] = old_home
