try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

from rpmspectool import version


def test_version():
    assert version.version == metadata.version("rpmspectool")
