#!/usr/bin/env python

from gmp import *

uni_repos = []
uni_repos.extend(SSHDir("peer.zerties.org", "uni").into("/tmp/uni/"))

r = RepoManager()
r.add_set("uni", uni_repos)

r()


