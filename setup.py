from __future__ import print_function

import sys

from setuptools import find_packages, setup

if sys.version_info.major < 3:
    print("Python versions older than 3 are not supported.", file=sys.stderr)
    sys.exit(1)

setup(
    name="rpmspectool",
    version="1.99.4",
    author="Nils Philippsen",
    author_email="nils@redhat.com",
    url="https://github.com/nphilipp/rpmspectool",
    download_url="https://pypi.python.org/pypi/rpmspectool",
    install_requires=["pycurl"],
    packages=find_packages(),
    include_package_data=True,
    scripts=["scripts/rpmspectool"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Topic :: Software Development :: Build Tools",
        ],
    )
