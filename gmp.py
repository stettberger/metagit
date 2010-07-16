import os
from socket import getfqdn
import re
import sys
import subprocess
import unittest
import functools

class Repository:
    clone_url = None
    local_url = None

    # This is a list of tuples, whith policies
    # A Policiy is a Tuple of (TYPE, Regexp) where the Regexp is
    # compared against the hostname. TYPE \in ["allow", "deny"]

    policies = []

    # Git options is a hash from git-<command> to a list of options
    git_options = {}

    def __init__(self, clone_url, local_url = None, into = ".", default_policy = "allow"):
        self.clone_url = clone_url
        # If no local_url is specified, we use the last part of the clone url
        # without the .git
        if local_url == None:
            m = re.match(".*/([^/]*)$", clone_url)
            if m:
                self.local_url = os.path.join(into, m.group(1).replace(".git", ""))
            else:
                self.local_url = into
        else:
            if local_url[-1] == '/':
                local_url = local_url[0:-1]
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

    def get_state(self):
        if os.path.exists(self.local_url + "/.git"):
            return "+"
        elif os.path.exists(self.local_url):
            return "N"
        else:
            return "-"


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
        self.assertEqual(Repository("foo/bar/baz/das.git").local_url, "./das")
        self.assertEqual(Repository("foo/bar/baz/das").local_url, "./das")

class SSHDir:
    clone_urls = None

    def __init__(self, host, directory):
        self.host = host
        self.directory = directory

    def urls(self):
        if self.clone_urls == None:
            self.__get_list();
        return self.clone_urls

    def __get_list(self):
        process = subprocess.Popen(["ssh", self.host, "find", self.directory, 
                                    "-maxdepth", "2", "-type", "d",
                                    "-iname", ".git"], 
                                   stdout = subprocess.PIPE,
                                   stderr = subprocess.PIPE)
        process.stderr.close()
        self.clone_urls = []
        for repo in process.stdout.readlines():
            m = re.match("(.*)/\.git", repo)
            self.clone_urls.append(self.host + ":" + m.group(1))
        
    def into(self, local_directory):
        return [Repository(url, into = local_directory) for url in self.urls()]

class RepoManager:
    sets = {}

    def __init__(self):
        self.hostname = getfqdn()

    def __call__(self):
        args = sys.argv[1:]
        if len(args) < 1:
            self.die("Too less arguments")
        self.commands = {"list": self.list,
                    "clone": self.clone,
                    "foreach": self.foreach,
                    "status" : self.shortcut("status")}
        if args[0] in self.commands:
            self.commands[args[0]](args[1:])
        else:
            self.die("Command not found: " + args[0])

    def die(self, msg):
        print msg
        print
        print "Commands: " + ", ".join(self.commands.keys())
        
        sys.exit(-1)


    def add_set(self, set_name, repo_list):
        if not set_name in self.sets:
            self.sets[set_name] = []
        self.sets[set_name].extend(repo_list)

    def _select(self, selector):
        selector = ".*" + selector
        repos = []
        for s in self.sets.keys():
            for repo in self.sets[s]:
                if (selector == ".*all" or re.match(selector, s + ":" + repo.clone_url)) \
                        and repo.check_policy(self.hostname):
                    repos.append(repo)
        return repos
    
    def list(self, selector):
        if len(selector) == 0:
            selector = ["all"]
        repos = self._select(selector[0])
        for repo in repos:
            print(repo.get_state() + " " + repo.clone_url + " --> " + repo.local_url)
        
    def clone(self, selector):
        if len(selector) == 0:
            selector = ["all"]

        repos = self._select(selector[0])
        for repo in repos:
            directory = os.path.dirname(repo.local_url)
            if not os.path.exists(directory):
                print("mkdir -p " + directory)
                os.makedirs(directory)
            if os.path.exists(repo.local_url):
                continue
            print repo.git_clone()
            a = subprocess.Popen(repo.git_clone(), shell = True)
            a.wait()

    def _shortcut(self, args):
        if len(args) == 0:
            return ["all"]
        return args

    def shortcut(self, git_command):
        return lambda x: self.foreach([self._shortcut(x)[0], git_command] + self._shortcut(x)[1:])

    def foreach(self, args):
        if len(args) < 2:
            self.die("Not enough arguments")
        repos = self._select(args[0])
        for repo in repos:
            if not os.path.exists(repo.local_url + "/.git"):
                continue
            os.chdir(repo.local_url)
            command = "git " + args[1] + " " + (" ".join(repo.git_option(args[1]))) + " " + " ".join(args[2:])
            print "cd %s; %s"%(repo.local_url, command)
            a = subprocess.Popen(command, shell = True)
            a.wait()
        


if __name__ == "__main__":
    print map(lambda x: x.git_clone(), SSHDir("peer.zerties.org", "uni").into("~/uni"))
    unittest.main()
