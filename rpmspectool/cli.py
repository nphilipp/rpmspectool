# -*- coding: utf-8 -*-
#
# rpmspectool.cli: CLI for rpmspectool
# Copyright © 2015, 2019 Red Hat, Inc.
# Copyright © 2017 Nils Philippsen <nils@tiptoe.de>

import argparse
import atexit
import logging
import os
import shutil
import sys
import tempfile
from logging import debug as log_debug
from logging import error as log_error

import argcomplete

from .download import DownloadError, download, is_url
from .rpm import RPMSpecEvalError, RPMSpecHandler
from .version import version


class IntListAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        int_list = []
        for item in values.split(","):
            try:
                int_list.append(int(item))
            except ValueError:
                try:
                    start, end = (int(x) for x in item.split("-", 1))
                except (TypeError, ValueError):
                    raise argparse.ArgumentError(self, f"can't convert {item!r} to list of ints")
                else:
                    int_list.extend(list(range(start, end + 1)))

        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, int_list)
        else:
            getattr(namespace, self.dest).extend(int_list)


class CLI(object):
    def _rm_tmpdir(self):
        def onerror(func, path, exc_info):
            log_error("Couldn't remove '%s': %s", path, exc_info)

        shutil.rmtree(self._tmpdir, onerror=onerror)

    @property
    def tmpdir(self):
        if not hasattr(self, "_tmpdir"):
            self._tmpdir = tempfile.mkdtemp(prefix="rpmspectool_")
            log_debug("Created temporary directory '%s'", self._tmpdir)
            if not self.args.debug:
                atexit.register(self._rm_tmpdir)
        return self._tmpdir

    def get_arg_parser(self):
        parser = argparse.ArgumentParser(description="Utility for RPM spec files")
        parser.add_argument("--debug", "-D", action="store_true")

        commands = parser.add_subparsers(dest="cmd", help="Commands")

        action_parser = argparse.ArgumentParser(add_help=False)
        action_parser.add_argument("--verbose", "-v", action="store_true")
        action_parser.add_argument("--define", "-d", action="append", default=[])

        source_group = action_parser.add_mutually_exclusive_group()
        source_group.add_argument("--sources", "-S", action="store_true")
        source_group.add_argument("--source", "-s", action=IntListAction, type=str)

        patches_group = action_parser.add_mutually_exclusive_group()
        patches_group.add_argument("--patches", "-P", action="store_true")
        patches_group.add_argument("--patch", "-p", action=IntListAction, type=str)

        action_parser.add_argument(
            "specfile", type=argparse.FileType("rb"), help="The RPM spec file to read"
        )

        get_cmd = commands.add_parser("get", parents=[action_parser], help="Download files")
        get_cmd.add_argument("--insecure", action="store_true", default=False)
        get_cmd.add_argument("--force", "-f", action="store_true", default=False)
        get_cmd.add_argument("--dry-run", "--dryrun", "-n", action="store_true", default=False)

        get_src_group = get_cmd.add_mutually_exclusive_group()
        get_src_group.add_argument("--directory", "-C", action="store")
        get_src_group.add_argument("--sourcedir", "-R", action="store_true")

        commands.add_parser("list", parents=[action_parser], help="List files")

        version_cmd = commands.add_parser("version", help="Show rpmspectool version")
        version_cmd.set_defaults(cmd="version")

        return parser

    def filter_sources_patches(self, args, spec_sources, spec_patches):
        if args.source:
            sources = {x: spec_sources[x] for x in args.source if x in spec_sources}
        elif args.sources:
            sources = spec_sources
        else:
            sources = None

        if args.patch:
            patches = {x: spec_patches[x] for x in args.patch if x in spec_patches}
        elif args.patches:
            patches = spec_patches
        else:
            patches = None

        if sources is None and patches is None:
            # Neither of --sources/--source/--patches/--patch was specified,
            # default to all
            sources = spec_sources
            patches = spec_patches

        sources = sources or {}
        patches = patches or {}

        return sources, patches

    def main(self):
        argparser = self.get_arg_parser()
        argcomplete.autocomplete(argparser)
        args = self.args = argparser.parse_args(sys.argv[1:])

        if args.debug:
            logging.basicConfig(level=logging.DEBUG)

        log_debug("args: %s", args)

        if not getattr(args, "cmd"):
            argparser.print_usage()
        elif args.cmd == "version":
            print(f"{sys.argv[0]} {version}")
        else:
            parsed_spec_path = os.path.join(
                self.tmpdir, "rpmspectool-" + os.path.basename(self.args.specfile.name)
            )
            spechandler = RPMSpecHandler(self.tmpdir, args.specfile, parsed_spec_path)

            try:
                specfile_res = spechandler.eval_specfile(self.args.define)
            except RPMSpecEvalError as e:
                specpath, returncode, stderr = e.args
                if args.debug:
                    print(f"Error parsing intermediate spec file '{specpath}'.", file=sys.stderr)
                else:
                    print("Error parsing intermediate spec file.", file=sys.stderr)
                if args.verbose:
                    print(f"RPM error:\n{stderr}", file=sys.stderr)
                sys.exit(2)

            sources, patches = self.filter_sources_patches(
                args, specfile_res["sources"], specfile_res["patches"]
            )

            if args.cmd == "list":
                for prefix, what in (("Source", sources), ("Patch", patches)):
                    for i in sorted(what):
                        print(f"{prefix}{i}: {what[i]}")
            else:  # args.cmd == "get"
                if getattr(args, "sourcedir"):
                    where = specfile_res["srcdir"]
                else:
                    where = getattr(args, "directory")
                for what in sources, patches:
                    for i in sorted(what):
                        url = what[i]
                        if is_url(url):
                            try:
                                download(
                                    url,
                                    where=where,
                                    dry_run=args.dry_run,
                                    insecure=args.insecure,
                                    force=args.force,
                                )
                            except DownloadError as e:
                                log_error(e.args[0])
                                return 1
                            except FileExistsError as e:
                                log_error(
                                    e.args[1] + f": {e.filename}"
                                    if e.filename
                                    else "" + f", {e.filename2}"
                                    if e.filename2
                                    else ""
                                )
                                return 1

        return 0


def main():
    try:
        return CLI().main()
    except KeyboardInterrupt:
        return 1
