import pkg_resources


try:
    version = pkg_resources.require('rpmspectool')[0].version
except pkg_resources.DistributionNotFound:
    version = 'git'
