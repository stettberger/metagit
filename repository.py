import os
import re
from policy import PolicyMixin

class Repository (PolicyMixin):
    """A Repository instance represents exactly one repository"""

    aliases = {}

    def __init__(self, clone_url, local_url = None, into = ".", default_policy = "allow"):
        """clone_url: the url which is used to clone the repository
local_url: to this directory the repository is cloned
into: if local_url is null, the repository is cloned into the <into> directory, and the 
      repository name is appended (without the .git)
default_policy: defines if the repo can be cloned on all machines ("allow") or not 
      ("deny"). See add_policy and check_policy for details"""

        PolicyMixin.__init__(self, default_policy)

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
            self.policies[0][1])

        ret += self.policy_serialize()

        for cmd in self.git_options.keys():
            for option in self.git_options[cmd]:
                ret += ".add_git_option('%s', '%s')" %( cmd.replace("'", "\\'"),
                                                        option.replace("'", "\\'"))
        return ret

    def status_line(self):
        return (self.get_state() + " " + self.clone_url + " --> " + self.local_url)

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
    def __init__(self, clone_url, local_url = None, into = ".", default_policy = "allow", repo_name = None):
        if not local_url:
            local_url = os.path.join(into, repo_name)
        Repository.__init__(self, clone_url, local_url, into, default_policy)

