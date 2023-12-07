import argparse
import stat
import sys
import tempfile
from contextlib import nullcontext
from errno import EEXIST
from io import IOBase
from pathlib import Path
from unittest import mock

import pytest

from rpmspectool import cli, download as download_mod, version

HERE = Path(__file__).parent
TEST_SPEC_PATH = HERE / "test-data" / "test1.spec"
TEST_EXPECTED_PATH = HERE / "test-data" / "test1.expected"

SPECFILE = object()


@pytest.fixture(autouse=True)
def cleanable_mkdtemp(tmpdir):
    """Cause mkdtemp calls to use the pytest temporary directory by default."""
    real_mkdtemp = tempfile.mkdtemp

    def wrapping_mkdtemp(*args, **kwargs):
        if (len(args) < 3 or not args[2]) and not kwargs.get("dir"):
            args = args[:2]
            kwargs["dir"] = tmpdir
        return real_mkdtemp(*args, **kwargs)

    with mock.patch.object(tempfile, "mkdtemp", new=wrapping_mkdtemp):
        yield


class TestCLI:
    @pytest.mark.parametrize("with_error", (False, True), ids=("without-error", "with-error"))
    def test__rm_tmpdir(self, with_error, tmp_path, caplog):
        tree_to_remove = tmp_path / "tree"
        tree_to_remove.mkdir()
        if with_error:
            old_mode = stat.S_IMODE(tree_to_remove.stat().st_mode)
            tree_to_remove.chmod(0o000)

        cli_obj = cli.CLI()
        cli_obj._tmpdir = str(tree_to_remove)

        cli_obj._rm_tmpdir()

        if with_error:
            tree_to_remove.chmod(old_mode)
            assert f"Couldn't remove '{tree_to_remove}'" in caplog.text

    @pytest.mark.parametrize(
        "args, expected",
        (
            (
                ("get", SPECFILE),
                {
                    "cmd": "get",
                    "debug": False,
                    "verbose": False,
                    "define": [],
                    "sources": False,
                    "source": None,
                    "patches": False,
                    "patch": None,
                    "insecure": False,
                    "force": False,
                    "dry_run": False,
                    "directory": None,
                    "sourcedir": False,
                    "specfile": SPECFILE,
                },
            ),
            (("--debug", "get", SPECFILE), {"cmd": "get", "debug": True, "specfile": SPECFILE}),
            (
                ("get", "--verbose", SPECFILE),
                {"cmd": "get", "verbose": True, "specfile": SPECFILE},
            ),
            (
                ("get", "--define", "foo bar", "-d", "bar baz", SPECFILE),
                {"cmd": "get", "define": ["foo bar", "bar baz"], "specfile": SPECFILE},
            ),
            (
                ("get", "--sources", SPECFILE),
                {"cmd": "get", "sources": True, "source": None, "specfile": SPECFILE},
            ),
            (
                ("get", "--source", "1", "-s", "2", SPECFILE),
                {"cmd": "get", "sources": False, "source": [1, 2], "specfile": SPECFILE},
            ),
            (
                ("get", "--patches", SPECFILE),
                {"cmd": "get", "patches": True, "patch": None, "specfile": SPECFILE},
            ),
            (
                ("get", "--patch", "3", "-p", "4", SPECFILE),
                {"cmd": "get", "patches": False, "patch": [3, 4], "specfile": SPECFILE},
            ),
            (
                ("get", "--insecure", SPECFILE),
                {"cmd": "get", "insecure": True, "specfile": SPECFILE},
            ),
            (
                ("get", "--force", SPECFILE),
                {"cmd": "get", "force": True, "specfile": SPECFILE},
            ),
            (
                ("get", "--dry-run", SPECFILE),
                {"cmd": "get", "dry_run": True, "specfile": SPECFILE},
            ),
            (
                ("get", "--directory", "/boo", SPECFILE),
                {"cmd": "get", "directory": "/boo", "specfile": SPECFILE},
            ),
            (
                ("get", "--sourcedir", SPECFILE),
                {"cmd": "get", "sourcedir": True, "specfile": SPECFILE},
            ),
            (("list", SPECFILE), {"cmd": "list", "debug": False, "specfile": SPECFILE}),
            (
                ("list", "--source", "1-3", SPECFILE),
                {"cmd": "list", "source": [1, 2, 3], "specfile": SPECFILE},
            ),
            (("list", "--source", "boo", SPECFILE), argparse.ArgumentError),
            (("version",), {"cmd": "version"}),
        ),
    )
    def test_get_arg_parser(self, args, expected, tmp_path):
        empty_spec = tmp_path / "empty.spec"
        with empty_spec.open("w") as fp:
            print(file=fp)

        cli_obj = cli.CLI()

        parser = cli_obj.get_arg_parser()
        assert isinstance(parser, argparse.ArgumentParser)

        args = [str(empty_spec) if v is SPECFILE else v for v in args]

        if isinstance(expected, type) and issubclass(expected, Exception):
            expected_exception_ctx = pytest.raises(SystemExit)
        else:
            expected_exception_ctx = nullcontext()

        with expected_exception_ctx as excinfo:
            parsed = parser.parse_args(args)

        if not excinfo:
            for key, expected_value in expected.items():
                parsed_value = getattr(parsed, key)
                if isinstance(parsed_value, IOBase):
                    parsed_value = parsed_value.name

                if expected_value is SPECFILE:
                    expected_value = str(empty_spec)

                assert parsed_value == expected_value

    @pytest.mark.parametrize("testcase", (None, "sources", "source", "patches", "patch"))
    def test_filter_sources_patches(self, testcase):
        SPEC_SOURCES = {0: "hui", 1: "buh"}
        SPEC_PATCHES = {0: "foo", 1: "bar"}

        args = mock.Mock()
        args.source = [0] if testcase == "source" else None
        args.sources = testcase == "sources"
        args.patch = [1] if testcase == "patch" else None
        args.patches = testcase == "patches"

        sources, patches = cli.CLI().filter_sources_patches(args, SPEC_SOURCES, SPEC_PATCHES)

        match testcase:
            case None:
                assert sources == SPEC_SOURCES
                assert patches == SPEC_PATCHES
            case "sources":
                assert sources == SPEC_SOURCES
                assert not patches
            case "source":
                assert sources == {0: SPEC_SOURCES[0]}
                assert not patches
            case "patches":
                assert not sources
                assert patches == SPEC_PATCHES
            case "patch":
                assert not sources
                assert patches == {1: SPEC_PATCHES[1]}

    @pytest.mark.parametrize(
        "testcase",
        (
            "list",
            "list-debug",
            "list-eval-error",
            "list-eval-error-debug-verbose",
            "get",
            "get-debug",
            "get-sourcedir",
            "get-download-error",
            "get-file-exists-error",
            "version",
            "usage",
        ),
    )
    def test_main(self, testcase, caplog, capsys, tmp_path):
        caplog.set_level("DEBUG")
        TEST_SPEC = str(TEST_SPEC_PATH)
        with TEST_EXPECTED_PATH.open("r") as expected_fp:
            expected = expected_fp.read()

        base_argv = ["rpmspectool"]
        cli_obj = cli.CLI()

        expected_exc_context = nullcontext()

        global_args = []
        subcmd_args = []

        if "debug" in testcase:
            global_args.append("--debug")

        if "list" in testcase:
            subcmd_args.append("list")
        elif "get" in testcase:
            subcmd_args.append("get")
        elif "version" in testcase:
            subcmd_args.append("version")
        else:  # testcase == "usage"
            pass

        if "verbose" in testcase:
            subcmd_args.append("--verbose")

        if "sourcedir" in testcase:
            subcmd_args.extend(("--define", "_sourcedir /foo/bar", "--sourcedir"))

        if "list" in testcase or "get" in testcase:
            if "eval-error" in testcase:
                subcmd_args.append("/dev/null")
                expected_exc_context = pytest.raises(SystemExit)
            else:
                subcmd_args.append(TEST_SPEC)

        args = global_args + subcmd_args

        argparser = mock.Mock(wraps=cli_obj.get_arg_parser())

        with mock.patch.object(cli_obj, "get_arg_parser") as get_arg_parser, mock.patch.object(
            sys, "argv"
        ), mock.patch.object(cli, "logging") as logging, mock.patch.object(
            cli, "download"
        ) as download, expected_exc_context as excinfo:
            get_arg_parser.return_value = argparser
            if "download-error" in testcase:
                download.side_effect = download_mod.DownloadError("This didn’t work.")
            elif "file-exists-error" in testcase:
                download.side_effect = FileExistsError(
                    EEXIST,  # errno
                    "File exists",  # strerror
                    "/boop",  # filename
                    None,  # winerror
                    None,  # filename2
                )

            sys.argv = base_argv + args

            retval = cli_obj.main()

        stdout, stderr = capsys.readouterr()

        if "get" not in testcase:
            download.assert_not_called()

        if "list" in testcase:
            if "debug" in testcase:
                logging.basicConfig.assert_called_once_with(level=logging.DEBUG)
            else:
                logging.basicConfig.assert_not_called()

            if "error" not in testcase:
                assert stdout == expected
            else:
                assert excinfo.value.code == 2
                assert "Error parsing intermediate spec file" in stderr
                if "verbose" in testcase:
                    assert "RPM error:" in stderr
        elif "get" in testcase:
            expected_source_calls = []
            expected_patch_calls = []
            for line in expected.split("\n"):
                if not line:
                    continue

                sourcepatch, url = line.split(":", 1)
                url = url.strip()
                scheme = url.split(":", 1)[0].lower()
                if scheme not in ("https", "http", "ftp"):
                    continue

                where = None
                if "sourcedir" in testcase:
                    where = "/foo/bar"

                expected_call = mock.call(
                    url, where=where, dry_run=False, insecure=False, force=False
                )
                if sourcepatch.lower().startswith("source"):
                    expected_source_calls.append(expected_call)
                else:
                    expected_patch_calls.append(expected_call)

            if "download-error" in testcase or "file-exists-error" in testcase:
                expected_source_calls = expected_source_calls[0:]
                expected_patch_calls = []

            assert download.call_args_list == expected_source_calls + expected_patch_calls

            if "error" in testcase:
                assert retval == 1
                if "download-error" in testcase:
                    assert "This didn’t work." in caplog.text
                else:
                    assert "File exists: /boop" in caplog.text
            else:
                assert not retval
        elif testcase == "version":
            assert stdout.rstrip() == f"{base_argv[0]} {version.version}"
        elif testcase == "usage":
            assert stdout.startswith("usage:")


@pytest.mark.parametrize(
    "with_keyboard_interrupt",
    (False, True),
    ids=("without-keyboard-interrupt", "with-keyboard-interrupt"),
)
def test_main(with_keyboard_interrupt):
    with mock.patch.object(cli, "CLI") as CLI:
        main_method = CLI.return_value.main
        if with_keyboard_interrupt:
            main_method.side_effect = KeyboardInterrupt()
        else:
            main_method.return_value = 0

        retval = cli.main()
        if with_keyboard_interrupt:
            assert retval == 1
        else:
            assert retval == 0

        main_method.assert_called_once_with()
