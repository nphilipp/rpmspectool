# -*- coding: utf-8 -*-
#
# rpmspectool.download: download handling for spectool
# Copyright © 2015 Red Hat, Inc.

import os
import re
from tempfile import NamedTemporaryFile
import time

import pycurl

from .i18n import _
from .version import version


class DownloadError(RuntimeError):
    pass


protocols_re = re.compile(r"^(?:ftp|https?)://", re.IGNORECASE)

def is_url(url):
    return bool(protocols_re.search(url))

def download(url, where=None, dry_run=False, insecure=False, force=False):
    if where is None:
        where = os.getcwd()

    assert(is_url(url))
    assert(not url.endswith("/"))

    fname = url.split("/")[-1]
    fpath = os.path.join(where, fname)

    if dry_run:
        print("NOT downloading {}' to '{}'".format(url, fpath))
        return

    with NamedTemporaryFile(dir=where, prefix=fname, mode="wb") as fobj:
        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.WRITEDATA, fobj)
        c.setopt(c.FOLLOWLOCATION, True)
        # request file modification time
        c.setopt(c.OPT_FILETIME, True)
        c.setopt(c.USERAGENT, "spectool/{}".format(version))
        if insecure:
            c.setopt(c.SSL_VERIFYPEER, False)
            c.setopt(c.SSL_VERIFYHOST, False)
        try:
            print("Downloading '{}' to '{}'".format(url, fpath))
            c.perform()
            ts = c.getinfo(c.INFO_FILETIME)
            http_status = c.getinfo(pycurl.HTTP_CODE)
            if not 200 <= http_status < 300:
                raise DownloadError(_("Couldn't download {}: {}".format(
                    url, http_status)))
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
