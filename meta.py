#!/usr/bin/env python

from gmp import *

peer_repos = []
peer_repos.append(Repository("peer.zerties.org:metagit", "~/metagit"))
peer_repos.append(Repository("peer.zerties.org:config", "~/"))


uni_repos = []
uni_repos.extend(SSHDir("qy03fugy@cip", "u").into("~/uni/"))

r = RepoManager()
r.add_set("uni", uni_repos)
r.add_set("peer", peer_repos)

r()


