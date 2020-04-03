from __future__ import print_function

import sys

from setuptools import setup


if sys.version_info.major < 3:
    print("Python versions older than 3 are not supported.", file=sys.stderr)
    sys.exit(1)


install_requires = [
    'argcomplete',
    'pycurl',
]


setup(
    name="rpmspectool",
    version="1.99.7",
    author="Nils Philippsen",
    author_email="nils@tiptoe.de",
    url="https://github.com/nphilipp/rpmspectool",
    download_url="https://pypi.python.org/pypi/rpmspectool",
    install_requires=install_requires,
    packages=['rpmspectool'],
    include_package_data=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Topic :: Software Development :: Build Tools",
    ],
    entry_points={
        'console_scripts': [
            'rpmspectool = rpmspectool.cli:main',
        ],
    },
    data_files=[
        ('share/bash-completion/completions', ['shell-completions/bash/rpmspectool']),
    ],
)
