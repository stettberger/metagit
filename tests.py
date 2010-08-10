#!/usr/bin/python

import unittest
from gmp import *

class RepositoryTestcase(unittest.TestCase):
    def setUp(self):
        self.repo = Repository("peer.zerites.org:config", "~/.git")
    def testPolicies(self):
        assert self.repo.check_policy("foobar") == True

        self.repo.add_policy("vamos1", "deny")
        assert self.repo.check_policy("vamos1.i4.informatik.uni-erlangen.de") == False
        assert self.repo.check_policy("foobar") == True

    def testGitOptions(self):
        self.repo.add_option("clone", "--bare")
        self.repo.add_option("clone", ["--bare", "foo"])

        assert self.repo.option("clone") == "--bare --bare foo"

    def testLocalName(self):
        self.assertEqual(Repository("foo/bar/baz/das.git").local_url, "./das")
        self.assertEqual(Repository("foo/bar/baz/das").local_url, "./das")


if __name__ == "__main__":
    unittest.main()
