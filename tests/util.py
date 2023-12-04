import os
from contextlib import contextmanager


@contextmanager
def changed_directory(location):
    if not isinstance(location, str):
        location = str(location)

    previous = os.getcwd()

    try:
        os.chdir(location)
        yield
    except Exception:
        pass

    os.chdir(previous)
