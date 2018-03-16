#!/usr/bin/env python3

# The version is the latest git tag
import subprocess
from manpage import build_manpage
from setuptools import setup

a = subprocess.Popen("git tag | grep '^v' | tail -n 1", shell = True, stdout = subprocess.PIPE)
version = a.stdout.readline().decode().strip().replace("v", "")
a.wait()

setup(
    name='metagit',
    version= version,
    author = "Christian Dietrich",
    author_email = "stettberger@dokucode.de",
    description='managing big amount of git repositories',
    long_description = """With metagit you can define either scm repositories manually
by setting their clone url and where to put them or you can use a repository lister,
which searches on a remote site for repositories and adds them to the list. You can select
some of the listed repos and execute various scm commands on the in a single step.""",
	license = "GPLv3",
    url='http://github.com/stettberger/metagit/',
    packages=['gmp'],
    cmdclass = {'build_manpage': build_manpage},
    scripts=['bin/metagit'],
    zip_safe=False,
    data_files=[('share/man/man1', ['metagit.1'])]
)
