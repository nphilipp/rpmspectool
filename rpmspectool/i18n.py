# -*- coding: utf-8 -*-
#
# rpmspectool.i18n: Internationalisation support for rpmspectool
# Copyright © 2015 Red Hat, Inc.

import gettext as _gettext
import locale


def init():
    locale.setlocale(locale.LC_ALL, "")

catalog = _gettext.translation('rpmspectool', fallback=True)

_ = gettext = catalog.gettext
