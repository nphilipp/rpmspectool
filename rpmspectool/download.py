# -*- coding: utf-8 -*-
#
# rpmspectool.download: download handling for rpmspectool
# Copyright © 2015 Red Hat, Inc.

import os
import re
import time
from tempfile import NamedTemporaryFile

import pycurl

from .version import version

umask = os.umask(0)
os.umask(umask)


class DownloadError(RuntimeError):
    pass


protocols_re = re.compile(r"^(?:ftp|https?)://", re.IGNORECASE)


def is_url(url):
    return bool(protocols_re.search(url))


def download(url, where=None, dry_run=False, insecure=False, force=False):
    if where is None:
        where = os.getcwd()

    assert is_url(url)
    assert not url.endswith("/")

    fname = url.split("/")[-1]
    fpath = os.path.join(where, fname)

    if dry_run:
        print(f"NOT downloading '{url}' to '{fpath}'")
        return

    with NamedTemporaryFile(dir=where, prefix=fname, mode="wb") as fobj:
        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEDATA, fobj)
        c.setopt(c.FOLLOWLOCATION, True)
        # request file modification time
        c.setopt(c.OPT_FILETIME, True)
        c.setopt(c.USERAGENT, f"rpmspectool/{version}")
        if insecure:
            c.setopt(c.SSL_VERIFYPEER, False)
            c.setopt(c.SSL_VERIFYHOST, False)
        try:
            print(f"Downloading '{url}' to '{fpath}'")
            c.perform()
            ts = c.getinfo(c.INFO_FILETIME)
            http_status = c.getinfo(pycurl.HTTP_CODE)
            if not 200 <= http_status < 300:
                raise DownloadError(f"Couldn't download {url}: {http_status}")
        finally:
            c.close()

        if force:
            try:
                os.remove(fpath)
            except FileNotFoundError:
                pass
        os.link(fobj.name, fpath)

    # set file modification time
    if ts != -1:
        os.utime(fpath, (time.time(), ts))
    # NamedTemporaryFile sets mode to 0600, change it to default per umask
    os.chmod(fpath, 0o666 & ~umask)
