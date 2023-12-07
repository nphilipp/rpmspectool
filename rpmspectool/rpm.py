# -*- coding: utf-8 -*-
#
# rpmspectool.rpm: RPM spec handling for rpmspectool
# Copyright © 2015 Red Hat, Inc.

import re
from collections import defaultdict
from functools import lru_cache
from logging import debug as log_debug
from subprocess import DEVNULL, PIPE, Popen


class RPMSpecEvalError(Exception):
    pass


class RPMSpecHandler(object):
    rpmcmd = "rpm"
    rpmbuildcmd = "rpmbuild"

    macro_re = re.compile(rb"^\s*%(?P<name>\w+)")
    archstuff_re = re.compile(
        rb"\s*(BuildArch(itectures)?|Exclu(d|siv)e(Arch|OS)|Icon)\s*:", re.IGNORECASE
    )
    copyright_re = re.compile(rb"^\s*Copyright\s*:", re.IGNORECASE)
    serial_re = re.compile(rb"^\s*Serial\s*:", re.IGNORECASE)
    source_patch_re = re.compile(
        rb"^\s*(?P<sourcepatch>Source|Patch)(?P<index>\d+)?\s*:" rb"\s*(?P<fileurl>.*\S)\s*$",
        re.IGNORECASE,
    )
    group_re = re.compile(rb"^\s*Group\s*:", re.IGNORECASE)
    srcdir_re = re.compile(rb"^\s*srcdir\s*:\s*(?P<srcdir>.*\S)\s*$", re.IGNORECASE)

    preamble_delimiters = {
        n.encode("utf-8")
        for n in (
            # part names
            "package",
            "prep",
            "generate_buildrequires",
            "conf",
            "build",
            "install",
            "check",
            "clean",
            "preun",
            "postun",
            "pretrans",
            "posttrans",
            "preuntrans",
            "postuntrans",
            "pre",
            "post",
            "files",
            "changelog",
            "description",
            "triggerpostun",
            "triggerprein",
            "triggerun",
            "triggerin",
            "trigger",
            "verifyscript",
            "sepolicy",
            "filetriggerin",
            "filetrigger",
            "filetriggerun",
            "filetriggerpostun",
            "transfiletriggerin",
            "transfiletrigger",
            "transfiletriggerun",
            "transfiletriggerpostun",
            "end",
            "patchlist",
            "sourcelist",
            # problematic macros
            "python_subpackages",
        )
    }

    conditional_names = set(
        (x.encode("utf-8") for x in ("if", "ifos", "ifnos", "ifarch", "ifnarch"))
    )

    rpm_cmd_macros = ("_topdir", "_sourcedir", "_builddir", "_srcrpmdir", "_rpmdir")

    def __init__(self, tmpdir, in_specfile, out_specfile):
        self.tmpdir = tmpdir
        if isinstance(in_specfile, str):
            self.in_specfile_path = in_specfile
            self.in_specfile = open(in_specfile, "rb")
        else:
            self.in_specfile_path = in_specfile.name
            self.in_specfile = in_specfile

        if isinstance(out_specfile, str):
            self.out_specfile_path = out_specfile
            self.out_specfile = open(out_specfile, "wb")
        else:
            self.out_specfile_path = out_specfile.name
            self.out_specfile = out_specfile

    def eval_specfile(self, definitions=()):
        log_debug("eval_specfile()")

        log_debug("writing parsed file '%s'", self.out_specfile_path)

        cmdline = (self.rpmcmd, "--eval")

        for macro in self.rpm_cmd_macros:
            self.out_specfile.write(f"%undefine {macro}\n%define {macro} ".encode("utf-8"))
            with Popen(
                cmdline + (f"%{macro}\n",),
                stdin=DEVNULL,
                stdout=PIPE,
                stderr=DEVNULL,
                close_fds=True,
            ) as rpmpipe:
                self.out_specfile.write(rpmpipe.stdout.read())
        self.out_specfile.write(b"\n")

        for definition in definitions:
            self.out_specfile.write(f"%define {definition}\n".encode("utf-8"))

        if self.need_conditionals_quirk:
            self._write_conditionals_quirk()

        preamble = []
        group_seen = False
        conditional_depth = 0

        for line in self.in_specfile.readlines():
            m = self.macro_re.search(line)
            if m:
                name = m.group("name")
                if name in self.preamble_delimiters:
                    # unwind open conditional blocks
                    unwinding_lines = [b"%endif\n"] * conditional_depth
                    preamble.extend(unwinding_lines)
                    self.out_specfile.write(b"".join(unwinding_lines))

                    # we're only interested in the preamble
                    break
                elif name in self.conditional_names:
                    conditional_depth += 1
                elif name == b"endif":
                    conditional_depth -= 1

            # ignore arch specifics
            if self.archstuff_re.search(line):
                continue

            # replace legacy tags
            line = self.copyright_re.sub(rb"License", line)
            line = self.serial_re.sub(rb"Epoch", line)

            preamble.append(line)
            self.out_specfile.write(line)

            if self.group_re.search(line):
                group_seen = True

        self.in_specfile.close()

        if not group_seen:
            preamble.append(b"Group: rpmspectool\n")

        preamble_bytes = b"".join(preamble)

        self.out_specfile.write(
            b"%description\n%prep\ncat << EOF\n"
            + preamble_bytes
            + b"\nSrcDir: %{_sourcedir}\n"
            + b"EOF\n"
        )

        self.out_specfile.close()

        cmdline = [self.rpmbuildcmd]

        for macro in self.rpm_cmd_macros:
            cmdline.extend(("--define", f"{macro} {self.tmpdir}"))

        cmdline.extend(("--nodeps", "-bp", self.out_specfile_path))

        ret_dict = defaultdict(dict)

        sourcepatchidx = {b"source": -1, b"patch": -1}

        with Popen(cmdline, stdin=DEVNULL, stdout=PIPE, stderr=PIPE, close_fds=True) as rpm:
            stdout, stderr = rpm.communicate()
            if rpm.returncode:
                raise RPMSpecEvalError(self.out_specfile_path, rpm.returncode, stderr)

            for line in stdout.split(b"\n"):
                line = line.strip()
                m = self.source_patch_re.search(line)
                if m:
                    sourcepatch = m.group("sourcepatch").lower()
                    if sourcepatch == b"source":
                        log_debug("Found source: %r", line)
                        spdict = ret_dict["sources"]
                    else:
                        log_debug("Found patch: %r", line)
                        spdict = ret_dict["patches"]
                    try:
                        index = int(m.group("index"))
                    except TypeError:
                        index = sourcepatchidx[sourcepatch] + 1
                    sourcepatchidx[sourcepatch] = index
                    spdict[index] = m.group("fileurl").decode("utf-8")
                m = self.srcdir_re.search(line)
                if m:
                    ret_dict["srcdir"] = m.group("srcdir").decode("utf-8")

        return ret_dict

    @staticmethod
    @lru_cache(None)
    def _get_need_conditionals_quirk(rpmcmd):
        cmdline = (rpmcmd, rpmcmd, "--eval", "%{?defined:1}%{!?defined:0}")
        with Popen(cmdline, stdin=DEVNULL, stdout=PIPE, stderr=DEVNULL) as rpm_pipe:
            return b"1" not in rpm_pipe.stdout.read()

    @property
    def need_conditionals_quirk(self):
        return self._get_need_conditionals_quirk(rpmcmd=self.rpmcmd)

    def _write_conditionals_quirk(self):
        self.out_specfile.write("# RPM conditionals quirk\n".encode("utf-8"))
        for macro, expansion in (
            ("defined", "%%{?%{1}:1}%%{!?%{1}:0}"),
            ("undefined", "%%{?%{1}:0}%%{!?%{1}:1}"),
            ("with", "%%{?with_%{1}:1}%%{!?with_%{1}:0}"),
            ("without", "%%{?with_%{1}:0}%%{!?with_%{1}:1}"),
            ("bcond_with", "%%{?_with_%{1}:%%global with_%{1} 1}"),
            ("bcond_without", "%%{!?_without_%{1}:%%global with_%{1} 1}"),
        ):
            self.out_specfile.write(
                f"%undefine {macro}\n%define {macro}() %{{expand:{expansion}}}\n".encode("utf-8")
            )
