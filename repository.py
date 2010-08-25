import os
import re
from policy import PolicyMixin

class Repository (PolicyMixin):
    """A Repository instance represents exactly one repository"""

    STATE_EXISTS = '+'
    STATE_BARE = 'b'
    STATE_NOT_EXISTS = '-'
    STATE_NO_REPO = 'N'

    aliases = {}

    def __init__(self, clone_url, local_url = None, into = ".", default_policy = "allow", scm = "git"):
        """clone_url: the url which is used to clone the repository
local_url: to this directory the repository is cloned
into: if local_url is null, the repository is cloned into the <into> directory, and the 
      repository name is appended (without the .git)
default_policy: defines if the repo can be cloned on all machines ("allow") or not 
      ("deny"). See add_policy and check_policy for details"""

        PolicyMixin.__init__(self, default_policy)

        # Git options is a hash from git-<command> to a list of options
        self.options = {}

        # Save what kind of source control we use
        self.scm = scm

        # After initialisation we aren't in any set
        self.set = []

        self.clone_url = clone_url
        # If no local_url is specified, we use the last part of the clone url
        # without the .git
        if local_url == None:
            m = re.match(".*/([^/]*)$", clone_url)
            if m:
                # Remove .git / .hg or whatever
                self.local_url = os.path.join(into, m.group(1).replace(".%s" % scm, ""))
            else:
                self.local_url = into
        else:
            if local_url[-1] == '/':
                local_url = local_url[0:-1]
            self.local_url = local_url

        self.local_url = os.path.expanduser(self.local_url)


        
    def add_option(self, command, option):
        """Adds generic options for a git <command> for this repository
e.g add_git_option("status", "-s") will always add the -s if you `metagit status'
the repository"""
        if not command in self.options:
            self.options[command] = []
        if isinstance(option, (list,tuple)):
            self.options[command].extend(option)
        else:
            self.options[command].append(option)

        return self

    def option(self, command):
        """Get all git_options() for a specific command. (See add_option)"""
        if not command in self.options:
            return ""
        return " ".join(self.options[command])

    def exec_string(self, command, args = []):
        """Produces an shell command for <command> + <args>"""
        # Escape all ' characters
        args = ["'" + x.replace("'", "\\'") + "'" for x in args]
        return " ".join([self.scm, self.alias(command), self.option(command)] + args)

    def clone(self):
        """Returns a git clone command as a string"""
        return self.exec_string("clone", [self.clone_url, self.local_url])

    def __str__(self):
        """A Repository can be serialized"""
        ret = "%s('%s', '%s', default_policy = '%s', scm = '%s')" %( 
            self.__class__.__name__,
            self.clone_url.replace("'", "\\'"),
            self.local_url.replace("'", "\\'"),
            self.policies[0][1],
            self.scm)

        ret += self.policy_serialize()

        for cmd in self.options.keys():
            for option in self.options[cmd]:
                ret += ".add_option('%s', '%s')" %( cmd.replace("'", "\\'"),
                                                    option.replace("'", "\\'"))
        return ret

    def status_line(self):
        sets = ":".join(self.set)
        if sets != "":
            sets = ":" + sets
        return "%s (%s%s) %s --> %s" % (self.get_state(), self.scm, sets, self.clone_url, self.local_url)

    def get_state(self):
        """'+' if the repository exists
'N' if the destination directory exists but isn't a git repo
'-' if the destination doesn't exists"""
        if os.path.exists(os.path.join(self.local_url, "." + self.scm)):
            return self.STATE_EXISTS
        elif os.path.exists(os.path.join(self.local_url, "refs")):
            return self.STATE_BARE
        elif os.path.exists(self.local_url):
            return self.STATE_NO_REPO
        else:
            return self.STATE_NOT_EXISTS

    def alias(self, command):
        """Lookup the command in the self.aliases and replace it if neccessary"""
        if command in self.aliases:
            return self.aliases[command]
        return command

class SVNRepository(Repository):
    """This Repository type replaces push/clone/pull with the git svn 
commands dcommit/clone/rebase, here only hg is permitted"""
    aliases = {"push": "svn dcommit",
               "clone": "svn clone",
               "pull": "svn rebase"}
    def __init__(self, clone_url, local_url = None, into = ".",  repo_name = None, **kwargs):
        if not local_url:
            local_url = os.path.join(into, repo_name)
        kwargs['scm'] = 'git'
        Repository.__init__(self, clone_url, local_url, into, **kwargs)

