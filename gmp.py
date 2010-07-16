import re
import subprocess
import unittest

class Repository:
    clone_url = None
    local_url = None

    # This is a list of tuples, whith policies
    # A Policiy is a Tuple of (TYPE, Regexp) where the Regexp is
    # compared against the hostname. TYPE \in ["allow", "deny"]

    policies = []

    # Git options is a hash from git-<command> to a list of options
    git_options = {}

    def __init__(self, clone_url, local_url = None, default_policy = "allow"):
        self.clone_url = clone_url
        # If no local_url is specified, we use the last part of the clone url
        # without the .git
        if local_url == None:
            m = re.match(".*/([^/]*)$", clone_url)
            if m:
                self.local_url = m.group(1).replace(".git", "")
            else:
                self.local_url = ""
        else:
            self.local_url = local_url
        self.policies += [(default_policy, ".*")]
        
    def add_policy(self, regexp, policy = "allow"):
        self.policies.append((policy, regexp))

    def check_policy(self, hostname):
        result = False
        for policy in self.policies:
            if re.match(policy[1], hostname) != None:
                if policy[0] == "allow":
                    result = True
                else:
                    result = False

        return result

    def add_git_option(self, command, option):
        if not command in self.git_options:
            self.git_options[command] = []
        if isinstance(option, (list,tuple)):
            self.git_options[command].extend(option)
        else:
            self.git_options[command].append(option)

    def git_option(self, command):
        if not command in self.git_options:
            return ""
        return " ".join(self.git_options[command])

    def git_clone(self):
        return "git clone %s %s %s" % (self.git_option("clone"),
                                       self.clone_url,
                                       self.local_url)


class RepositoryTestcase(unittest.TestCase):
    def setUp(self):
        self.repo = Repository("peer.zerites.org:config", "~/.git")
    def testPolicies(self):
        assert self.repo.check_policy("foobar") == True

        self.repo.add_policy("vamos1", "deny")
        assert self.repo.check_policy("vamos1.i4.informatik.uni-erlangen.de") == False
        assert self.repo.check_policy("foobar") == True

    def testGitOptions(self):
        self.repo.add_git_option("clone", "--bare")
        self.repo.add_git_option("clone", ["--bare", "foo"])

        assert self.repo.git_option("clone") == "--bare --bare foo"

    def testLocalName(self):
        self.assertEqual(Repository("foo/bar/baz/das.git").local_url, "das")
        self.assertEqual(Repository("foo/bar/baz/das").local_url, "das")

class SSHDir:
    def __init__(self, host, directory):
        process = subprocess.Popen(["ssh", host, "find", directory, 
                                    "-maxdepth", "2", "-type", "d",
                                    "-iname", ".git"], 
                                   stdout=subprocess.PIPE)
        process.stdin.close()
        for i in process.stdout.readlines():
            print i
        
    

if __name__ == "__main__":
    SSHDir("peer.zerties.org", "uni")
    unittest.main()
