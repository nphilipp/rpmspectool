import os
import time
from contextlib import nullcontext
from unittest import mock

import pycurl
import pytest

from rpmspectool import download, version

from .util import changed_directory


@pytest.mark.parametrize(
    "inval, retval",
    (
        ("ftp://boop", True),
        ("https://bar", True),
        ("HTTP://FROOP", True),
        ("ssh://hello", False),
    ),
)
def test_is_url(inval, retval):
    assert download.is_url(inval) == retval


def test_download_dry_run(capsys):
    test_url = "https://foo/bar"
    fname = test_url.split("/")[-1]
    cwd = os.getcwd()

    with mock.patch.object(download, "NamedTemporaryFile") as NamedTemporaryFile:
        download.download(test_url, dry_run=True)

    NamedTemporaryFile.assert_not_called()

    out, err = capsys.readouterr()
    assert not err
    assert out.rstrip() == f"NOT downloading '{test_url}' to '{cwd}/{fname}'"


@pytest.mark.parametrize("where", (None, "tmpdir"), ids=("without-where", "with-where"))
@pytest.mark.parametrize("insecure", (None, True), ids=("secure", "insecure"))
@pytest.mark.parametrize("timestamp", (-1, 10**9), ids=("without-timestamp", "with-timestamp"))
@pytest.mark.parametrize(
    "success, force",
    (
        (True, False),
        (True, True),
        (True, "filenotfound"),
        (False, False),
    ),
    ids=("success", "success-force", "success-force-filenotfound", "failure"),
)
@mock.patch("rpmspectool.download.pycurl.Curl")
@mock.patch("rpmspectool.download.NamedTemporaryFile")
def test_download(
    NamedTemporaryFile, Curl, where, insecure, force, timestamp, success, tmp_path, capsys
):
    test_url = "https://foo/bar"
    fname = test_url.split("/")[-1]
    fpath = str(tmp_path / fname)

    NamedTemporaryFile.return_value.__enter__.return_value = fobj = mock.Mock()
    fobj.name = str(tmp_path / "tmp-file")

    Curl.return_value = curl = mock.Mock()

    if success:
        http_status = 200
        expect_download_error = nullcontext()
    else:
        http_status = 404
        expect_download_error = pytest.raises(download.DownloadError)

    def mock_getinfo(arg):
        if arg == pycurl.HTTP_CODE:
            return http_status

        if arg == curl.INFO_FILETIME:
            return timestamp

        return mock.Mock()

    curl.getinfo.side_effect = mock_getinfo

    if where is None:
        chdir_ctx = changed_directory(tmp_path)
    else:
        where = str(tmp_path)
        chdir_ctx = nullcontext()

    time_now = time.time()

    with mock.patch.object(time, "time") as time_time, mock.patch.object(
        os, "remove"
    ) as os_remove, mock.patch.object(os, "link") as os_link, mock.patch.object(
        os, "utime"
    ) as os_utime, mock.patch.object(
        os, "chmod"
    ) as os_chmod, chdir_ctx, expect_download_error:
        time_time.return_value = time_now
        if force == "filenotfound":
            force = True
            os_remove.side_effect = FileNotFoundError(fpath)
        download.download(test_url, where=where, insecure=insecure, force=force)

    curl.perform.assert_called_once_with()
    curl.close.assert_called_once_with()

    setopt_expected_calls = [
        mock.call(curl.URL, test_url),
        mock.call(curl.WRITEDATA, fobj),
        mock.call(curl.FOLLOWLOCATION, True),
        mock.call(curl.OPT_FILETIME, True),
        mock.call(curl.USERAGENT, f"rpmspectool/{version.version}"),
    ]

    if insecure:
        setopt_expected_calls.extend(
            [
                mock.call(curl.SSL_VERIFYPEER, False),
                mock.call(curl.SSL_VERIFYHOST, False),
            ]
        )

    assert curl.setopt.call_args_list == setopt_expected_calls

    if success:
        if force:
            os_remove.assert_called_once_with(fpath)
        else:
            os_remove.assert_not_called()
        os_link.assert_called_once_with(fobj.name, fpath)
        if timestamp != -1:
            os_utime.assert_called_once_with(fpath, (time_now, timestamp))
        else:
            os_utime.assert_not_called()
        os_chmod.assert_called_once_with(fpath, 0o666 & ~download.umask)
    else:
        os_remove.assert_not_called()
        os_link.assert_not_called()
        os_utime.assert_not_called()
        os_chmod.assert_not_called()
