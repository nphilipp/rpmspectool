# -*- coding: utf-8 -*-
#
# rpmspectool.i18n: Internationalisation support for rpmspectool
# Copyright © 2015 Red Hat, Inc.

import gettext as _gettext
import locale


catalog = _gettext.translation('rpmspectool', fallback=True)

_ = gettext = catalog.gettext


def init():
    locale.setlocale(locale.LC_ALL, "")
