import subprocess
import os
from tools import *

class SCM:
    """SCM is the abstract base class which implements defines the
    interface a scm must implement to be used by the Repository
    class"""

    """The scm binary, e.g. "git" """
    binary = None

    """Aliases for scm command. e.g if defined clone: svn clone, every
    clone command will be replaced by svn clone"""
    aliases = {}

    STATE_EXISTS = '+'
    STATE_BARE = 'b'
    STATE_NOT_EXISTS = '-'
    STATE_NO_REPO = 'N'

    states = [STATE_EXISTS, STATE_BARE, STATE_NOT_EXISTS, STATE_NO_REPO]

    def __init__(self):
        # See Options
        self.options = {}


    #
    # Options: You can add a Option to a specific scm command if you
    # want to. e.g. add_option("pull", "--rebase") will always add a
    # rebase to your pull command
    #

    def add_option(self, command, option):
        """Adds generic options for a <scm> <command> for this repository
        e.g add_git_option("status", "-s") will always add the -s if you `metagit status'
        the repository"""
        if not command in self.options:
            self.options[command] = []
        if isinstance(option, (list,tuple)):
            self.options[command].extend(option)
        else:
            self.options[command].append(option)

        return self

    def __option(self, command):
        """Get all add_option() for a specific command. (See add_option)"""
        if not command in self.options:
            return ""
        return " ".join(self.options[command])

    #
    # Aliases
    # For easier adaption of other scms similar to the regular one
    # aliases for commands can be defined, e.g.
    # clone: svn clone; will always use `git svn clone' instead of
    # `git clone'. This is constant for a scm
    #
    def __alias(self, command):
        """Lookup the command in the self.aliases and replace it if neccessary"""
        if command in self.aliases:
            return self.aliases[command]
        return command

    #
    # Helper functions for executing things
    #
    def __exec_string(self, command, args = []):
        """Produces an shell command for <command> + <args>"""
        # Escape all ' characters
        args = ["'" + esc(x) + "'" for x in args]
        return " ".join([self.binary, self.__alias(command),
                         self.__option(command)] + args)
    def execute(self, command, args = [], destdir = None):
        """Will use the self.<command> function if there is one, or
        otherwise use __execute to do it directly"""
        if command in dir(self):
            getattr(self, command)(args = args, destdir = destdir)
            return
        self.bare_execute(command, args, destdir)

    def bare_execute(self, command, args = [], destdir = None):
        """Prints the command to stdout and executes it within a shell
        context. Everything will be fine escaped"""
        command = self.__exec_string(command, args)
        # Maybe we have to change the directory first
        if destdir:
            command = "cd '%s'; %s" %(esc(destdir), command)
        print command
        a = subprocess.Popen(command, shell = True)
        a.wait()
        return a

    # 
    # All subclasses must be serializable
    # 
    def __str__(self):
        ret = self.__class__.__name__ + "()"

        for cmd in self.options.keys():
            for option in self.options[cmd]:
                ret += ".add_option('%s', '%s')" %( esc(cmd),
                                                    esc(option))
        return ret

    def get_state(self, local_url):
        """'+' if the repository exists
           'N' if the destination directory exists but isn't a git repo
           '-' if the destination doesn't exists"""
        if os.path.exists(os.path.join(local_url, "." + self.binary)):
            return self.STATE_EXISTS
        elif os.path.exists(os.path.join(local_url, "refs")):
            return self.STATE_BARE
        elif os.path.exists(local_url):
            return self.STATE_NO_REPO
        else:
            return self.STATE_NOT_EXISTS


    #
    # Wrapper functions for scm commands, can be overriden by
    # subclassing. These functions will overide the normal execution function
    #
    def clone(self, args = [], destdir = None):
        [remote_repo, local_repo] = args
        """Calling this method will clone the remote_repo
        to the local url. This method will execute the command"""
        return self.bare_execute("clone", [remote_repo, local_repo])        
        
class Git(SCM):
    binary = "git"
    name = "git"
    def __init__(self):
        SCM.__init__(self)

git = Git()

class GitSvn(Git):
    """This Repository type replaces push/clone/pull with the git svn 
    commands dcommit/clone/rebase, here only hg is permitted"""
    aliases = {"push": "svn dcommit",
               "clone": "svn clone",
               "pull": "svn rebase"}

    name = "git-svn"

    def __init__(self, externals = []):
        Git.__init__(self)
        self.externals = externals

    def __externals(self, destdir):
        process = subprocess.Popen("cd '%s'; git svn propget svn:externals" % destdir,
                                   shell = True,
                                   stderr = subprocess.PIPE,
                                   stdout = subprocess.PIPE)
        externals = [ x.strip().split(" ") for x in process.stdout.readlines() if x != "\n" ]
        process.wait()
        return externals


    def execute(self, command, args, destdir = None):
        Git.execute(self, command,args = args, destdir = destdir)
        if command in self.externals:
            for [path, clone_url] in self.__externals(destdir):
                Git.execute(self, command, args = args,
                                  destdir = os.path.join(destdir, path))

    def clone(self, args, destdir = None):
        # Call the actual git svn clone (with aliases!)
        destdir = args[1]
        self.bare_execute("clone", args = args)
        
        fd = open(os.path.join(destdir, ".git/info/exclude"), "a+")
        fd.write("\n# Metagit svn external excludes\n")
        
        if "clone" in self.externals:
            for [path, clone_url] in self.__externals(destdir):
                local_url = os.path.join(destdir, path)
                fd.write(path + "/\n")
                self.bare_execute("clone", args = [clone_url, local_url])

git_svn = gitsvn = GitSvn()
git_svn_externals = gitsvn_externals = GitSvn(externals = ["clone", "pull", "push"])

class Mercurial(SCM):
    name = "hg"
    binary = "hg"
    def __init__(self):
        SCM.__init__(self)
mercurial = hg = Mercurial()
