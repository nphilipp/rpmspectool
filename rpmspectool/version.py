try:
    version = __import__('pkg_resources').require('rpmspectool')[0].version
except:
    version = 'git'
