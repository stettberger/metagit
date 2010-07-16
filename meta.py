#!/usr/bin/env python

from gmp import *

peer_repos = []
peer_repos.append(Repository("peer.zerties.org:metagit", "~/metagit"))

uni_repos = []
uni_repos.extend(SSHDir("peer.zerties.org", "uni").into("/tmp/uni/"))

r = RepoManager()
r.add_set("uni", uni_repos)
r.add_set("peer", peer_repos)

r()


