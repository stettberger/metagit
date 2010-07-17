import os
from socket import getfqdn
import re
import sys
import subprocess
import unittest
import functools
import urllib2
from xml.dom.minidom import parse as xml_parse

class Repository:
    """A Repository instance represents exactly one repository"""

    aliases = {}

    def __init__(self, clone_url, local_url = None, into = ".", default_policy = "allow"):
        """clone_url: the url which is used to clone the repository
local_url: to this directory the repository is cloned
into: if local_url is null, the repository is cloned into the <into> directory, and the 
      repository name is appended (without the .git)
default_policy: defines if the repo can be cloned on all machines ("allow") or not 
      ("deny"). See add_policy and check_policy for details"""


        # This is a list of tuples, whith policies
        # A Policiy is a Tuple of (TYPE, Regexp) where the Regexp is
        # compared against the hostname. TYPE \in ["allow", "deny"]

        self.policies = []

        # Git options is a hash from git-<command> to a list of options
        self.git_options = {}

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

        self.local_url = os.path.expanduser(self.local_url)

        self.policies += [(default_policy, ".*")]

        
    def add_policy(self, regexp, policy = "allow"):
        """Adds a policy for a specific host. The fqdn of the local host will
be checked against the regexp here provided"""
        self.policies.append((policy, regexp))

        return self

    def check_policy(self, hostname):
        """In order, that you can't clone your big pr0n git into
your working directory you can define a policy for this repository, 
that it is only visible on your local machine."""
        result = False
        for policy in self.policies:
            if re.match(policy[1], hostname) != None:
                if policy[0] == "allow":
                    result = True
                else:
                    result = False

        return result

    def add_git_option(self, command, option):
        """Adds generic options for a git <command> for this repository
e.g add_git_option("status", "-s") will always add the -s if you `metagit status'
the repository"""
        if not command in self.git_options:
            self.git_options[command] = []
        if isinstance(option, (list,tuple)):
            self.git_options[command].extend(option)
        else:
            self.git_options[command].append(option)

        return self

    def git_option(self, command):
        """Get all git_options() for a specific command. (See add_git_option)"""
        if not command in self.git_options:
            return ""
        return " ".join(self.git_options[command])

    def git_clone(self):
        """Returns a git clone command as a string"""
        return "git %s %s %s %s" % (self.git_alias("clone"),
                                    self.git_option("clone"),
                                    self.clone_url,
                                    self.local_url)

    def __str__(self):
        """A Repository can be serialized"""
        ret = "%s('%s', '%s', default_policy = '%s')" %( 
            self.__class__.__name__,
            self.clone_url.replace("'", "\\'"),
            self.local_url.replace("'", "\\'"),
            self.policies[0][0])

        for policy in self.policies[1:]:
            ret += ".add_policy('%s', '%s')" %( policy[1].replace("'", "\\'"),
                                                policy[0].replace("'", "\\'"))
        for cmd in self.git_options.keys():
            for option in self.git_options[cmd]:
                ret += ".add_git_option('%s', '%s')" %( cmd.replace("'", "\\'"),
                                                        option.replace("'", "\\'"))
        return ret

    def get_state(self):
        """'+' if the repository exists
'N' if the destination directory exists but isn't a git repo
'-' if the destination doesn't exists"""
        if os.path.exists(self.local_url + "/.git"):
            return "+"
        elif os.path.exists(self.local_url):
            return "N"
        else:
            return "-"

    def git_alias(self, command):
        """Lookup the command in the self.aliases and replace it if neccessary"""
        if command in self.aliases:
            return self.aliases[command]
        return command

class SVNRepository(Repository):
    """This Repository type replaces push/clone/pull with the git svn 
commands dcommit/clone/rebase"""
    aliases = {"push": "svn dcommit",
               "clone": "svn clone",
               "pull": "svn rebase"}


#
# Repository Lister Services
#

class RepoLister:
    listers = []

    def __init__(self, cache = None):
        RepoLister.listers.append(self)
        if cache:
            self.cache = os.path.expanduser(cache)
        else:
            self.cache = None

        self.clone_urls = None
        self.local_directory = None

    def urls(self):
        """Retures a list of clone urls in the SSHDir"""
        if self.clone_urls == None:
            self.get_list()
        return self.clone_urls

    def get_list(self):
        pass

    def __iter__(self):
        if self.cache:
            # There may be a Repository Cache
            if os.path.exists(self.cache):
                try:
                    cache = open(self.cache)
                    repos = eval(cache.read())
                    cache.close()
                    return repos.__iter__()
                except:
                    print "WARNING: Invalid cache file: " + self.cache
                    # Disabling Cache
                    self.cache = None
            
        # Cache does not exist try to build it
        repos = [Repository(url, into = self.local_directory) for url in self.urls()]
        if self.cache:
            cache = open(self.cache, "w+")
            cache.write("[%s" % str(repos[0]))
            for r in repos[1:]:
                cache.write(",\n %s" % str(r))
            cache.write("]")
            cache.close()
        return repos.__iter__()

    def into(self, local_directory):
        """Uses the urls() list to create a list of Repositories, which will be located 
at <local_directory>/<remote_dir_name>"""
        self.local_directory = local_directory
        return self

class SSHDir(RepoLister):
    """With you can create SSHDir a list of git repositories on an remote host"""

    def __init__(self, host, directory, cache = None):
        """host: ssh login used with ssh
directory: remote directory where the git repos are searched"""
        RepoLister.__init__(self, cache)
        self.host = host
        self.directory = directory


    def get_list(self):
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
            
        
class Github(RepoLister):
    def __init__(self, username, protocol="ssh", cache = None):
        """Uses a github account name to get a list of repositories
username: github.com username
protocol: used for cloning the repository (choices: ssh/https/git)"""
        RepoLister.__init__(self, cache)
        self.username = username
        self.protocol = protocol

    def get_list(self):
        xml = urllib2.urlopen("http://github.com/api/v1/xml/%s"%self.username)
        repos = xml_parse(xml).getElementsByTagName("repository")
        self.clone_urls = []
        for repo in repos:
            name = repo.getElementsByTagName("name")[0].childNodes[0].data
            url = ""
            if self.protocol == "ssh":
                url = "git@github.com:%s/%s.git" % (self.username, name)
            elif self.protocol == "https":
                url = "https://%s@github.com/%s/%s.git" %(self.username, username, name)
            else:
                url = "git://github.com/%s/%s.git" %(self.username, name)

            self.clone_urls.append(url)

class RepoCache:
    caches = []

    def __init__(self, iteratable):
        pass

class RepoManager:
    """Manages all repositories and provides the command line interface"""
    sets = {}
    help_commands = {"selector": """A selector is a regexp which is checked against
<sets>:<clone-url> of a repository. So '^<set>:' will only select repositories within a given set."""}

    def __init__(self):
        self.hostname = getfqdn()
        self.commands = {"list": self.cmd_list,
                         "clone": self.cmd_clone,
                         "foreach": self.cmd_foreach,
                         "status" : self.shortcut("status"),
                         "push" : self.shortcut("push"),
                         "pull" : self.shortcut("pull"),
                         "fetch" : self.shortcut("fetch"),
                         "sets"  : self.cmd_sets,
                         "clean" : self.cmd_clean,
                         "help" : self.cmd_help}

    def __call__(self):
        """The Reposity Manager can be called in order to start the command
line interface"""
        args = sys.argv[1:]
        if len(args) < 1:
            self.die("Too less arguments")

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
        """You can add a list of repositories to a set"""
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
    
    def cmd_list(self, selector):
        """Lists all repositories, which matches the selector. If no selector given 
list all repositories. See help selector for help with selectors.

metagit list == metagit list all

usage: metagit list <selector>"""
        if len(selector) == 0:
            selector = ["all"]
        repos = self._select(selector[0])
        for repo in repos:
            print(repo.get_state() + " " + repo.clone_url + " --> " + repo.local_url)
        
    def cmd_clone(self, selector):
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

    def shortcut(self, git_command, help = None):
        if not help:
            help = "alias %s <selector> = foreach <selector> %s" %(git_command, git_command)
        func = lambda x: self.cmd_foreach([self._shortcut(x)[0], git_command] + self._shortcut(x)[1:])
        func.__doc__ = help
        return func

    def cmd_foreach(self, args):
        """usage: metagit foreach <selector> <git-command>
 executes git command on all repositories matching the selector

help selector for more information on selectors"""
        if len(args) < 2:
            self.die("Not enough arguments")
        repos = self._select(args[0])
        for repo in repos:
            if not os.path.exists(repo.local_url + "/.git"):
                continue
            os.chdir(repo.local_url)
            command = "git " + repo.git_alias(args[1]) + " " + (" ".join(repo.git_option(args[1]))) + " " + " ".join(args[2:])
            print "cd %s; %s"%(repo.local_url, command)
            a = subprocess.Popen(command, shell = True)
            a.wait()

    def cmd_sets (self, args):
        """Show only git repository sets"""
        if len(args) < 1:
            args = [".*all"]
        else:
            args[0] = ".*" + args[0]

        for key in self.sets.keys():
            if args[0] == ".*all" or re.match(args[0], key):
                print "%s:" % key
                for repo in self.sets[key]:
                    print "  " + repo.clone_url + " --> " + repo.local_url

    def cmd_clean(self, args):
        """Deletes all Cache files used by directory Listers"""
        for lister in RepoLister.listers:
            if lister.cache:
                os.unlink(lister.cache)

    def cmd_help(self, args):
        """recursive: see recursive"""
        if len(args) < 1:
            self.die("No topic selected")
        if args[0] in self.commands:
            doc = self.commands[args[0]].__doc__
            if doc:
                print doc
            else:
                self.die("No help available")

        elif args[0] in self.help_commands:
            print self.help_commands[args[0]]

        else:
            self.die("No help available")
