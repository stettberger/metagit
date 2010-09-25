#!/usr/bin/env python

from distutils.core import setup

# The version is the latest git tag
import subprocess
a = subprocess.Popen("git tag | grep '^v' | tail -n 1", shell = True, stdout = subprocess.PIPE)
version = a.stdout.readline().strip().replace("v", "")
a.wait()

setup(
    name='metagit',
    version= version,
	author = "Christian Dietrich",
	author_email = "stettberger@dokucode.de",
    description='managing big amount of git repositories',
	license = "GPLv3",
    url='http://github.com/stettberger/metagit/',
    packages=['gmp'],
    scripts=['metagit']
)
