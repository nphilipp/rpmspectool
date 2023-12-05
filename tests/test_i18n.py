from unittest import mock

from rpmspectool import i18n


@mock.patch("rpmspectool.i18n.locale")
def test_init(locale):
    i18n.init()

    locale.setlocale.assert_called_once_with(locale.LC_ALL, "")
