from unittest import mock

from pathlib import Path

import pytest

from rpmspectool import rpm

TEST_DATA = Path(__file__).parent / "test-data"


def get_test_data():
    retval = []

    for spec in TEST_DATA.glob("*.spec"):
        expected = spec.with_suffix(".expected")
        retval.append(pytest.param(spec, expected, id=spec.name))

    return retval


class TestRPMSpecHandler:
    @pytest.mark.parametrize("paramtype", ("str", "file"))
    def test___init__(self, paramtype, tmp_path):
        in_spec = tmp_path / "in.spec"
        out_spec = tmp_path / "out.spec"
        tmpdir = str(tmp_path)

        with in_spec.open("w") as fobj:
            print(file=fobj)

        if paramtype == "str":
            in_specfile = str(in_spec)
            out_specfile = str(out_spec)
        else:
            in_specfile = in_spec.open("rb")
            out_specfile = out_spec.open("wb")

        obj = rpm.RPMSpecHandler(tmpdir=tmpdir, in_specfile=in_specfile, out_specfile=out_specfile)

        assert obj.tmpdir == tmpdir
        assert obj.in_specfile_path == obj.in_specfile.name == str(in_spec)
        assert obj.out_specfile_path == obj.out_specfile.name == str(out_spec)

        obj.in_specfile.close()
        obj.out_specfile.close()

    @pytest.mark.parametrize(
        "with_definitions", (False, True), ids=("without-definitions", "with-definitions")
    )
    @pytest.mark.parametrize("with_quirk", (False, True), ids=("without-quirk", "with-quirk"))
    @pytest.mark.parametrize("spec, expected", get_test_data())
    def test_eval_specfile(self, spec, expected, with_quirk, with_definitions, tmp_path):
        in_specfile = str(spec)
        out_specfile_path = tmp_path / "out.spec"
        out_specfile = str(out_specfile_path)

        if with_definitions:
            definitions = ("a_test_macro a_test_macro_value", "another_test_macro another_value")
        else:
            definitions = ()

        handler = rpm.RPMSpecHandler(str(tmp_path), in_specfile, out_specfile)
        with mock.patch.object(
            rpm.RPMSpecHandler, "_get_need_conditionals_quirk"
        ) as _get_need_conditionals_quirk:
            _get_need_conditionals_quirk.return_value = with_quirk
            result = handler.eval_specfile(definitions=definitions)

        result_str = ""

        for key, kind in (("sources", "Source"), ("patches", "Patch")):
            for idx, url in result[key].items():
                result_str += f"{kind}{idx}: {url}\n"

        with expected.open("r") as expected_file:
            assert result_str == expected_file.read()

    def test_eval_broken_specfile(self, tmp_path):
        in_specfile = "/dev/null"
        out_specfile_path = tmp_path / "out.spec"
        out_specfile = str(out_specfile_path)

        handler = rpm.RPMSpecHandler(str(tmp_path), in_specfile, out_specfile)
        with pytest.raises(rpm.RPMSpecEvalError):
            handler.eval_specfile()

    @pytest.mark.parametrize(
        "needs_quirk", (False, True), ids=("without-needs-quirk", "with-needs-quirk")
    )
    def test_need_conditionals_quirk(self, needs_quirk, tmp_path):
        in_specfile_path = tmp_path / "in.spec"
        in_specfile = str(in_specfile_path)
        out_specfile_path = tmp_path / "out.spec"
        out_specfile = str(out_specfile_path)

        with in_specfile_path.open("w") as fp:
            fp.write("")

        handler = rpm.RPMSpecHandler(str(tmp_path), in_specfile, out_specfile)
        handler._get_need_conditionals_quirk.cache_clear()

        with mock.patch.object(rpm, "Popen") as Popen:
            Popen.return_value.__enter__.return_value = rpm_pipe = mock.Mock()
            rpm_pipe.stdout.read.return_value = b"0" if needs_quirk else b"1"

            assert handler.need_conditionals_quirk == needs_quirk
