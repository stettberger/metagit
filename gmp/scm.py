import subprocess
import re
import os

from tools import *

class SCM:
    """SCM is the abstract base class which implements defines the
    interface a scm must implement to be used by the Repository
    class"""

    """The scm binary, e.g. "git" """
    binary = None

    """The default metadata directory is .git"""
    metadata_dir = ".git"

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
        args = [esc(x) for x in args]
        return " ".join([self.binary, self.__alias(command),
                         self.__option(command)] + args)
    def execute(self, command, args = [], destdir = None):
        """Will use the self.<command> function if there is one, or
        otherwise use __execute to do it directly"""
        if command in dir(self):
            return getattr(self, command)(args = args, destdir = destdir)

        return self.bare_execute(command, args, destdir)

    def bare_execute(self, command, args = [], destdir = None):
        """Prints the command to stdout and executes it within a shell
        context. Everything will be fine escaped"""
        command = self.__exec_string(command, args)
        parallel = Options.opt("parallel")

        # Maybe we have to change the directory first
        if destdir:
            command = "cd %s; %s" %(esc(destdir), command)

        if parallel:
            command += " >/dev/null"

        a = execute(command)

        return [a]

    # 
    # All subclasses must be serializable
    # 
    def __str__(self):
        ret = self.__class__.__name__ + self.__str_keyword_arguments__()

        for cmd in self.options.keys():
            for option in self.options[cmd]:
                ret += ".add_option(%s, %s)" %(repr(cmd),
                                               repr(option))
        return ret

    def __str_keyword_arguments__(self):
        """For serializing a scm we also need to print all keyword arguments"""
        return "()"

    def get_state(self, local_url):
        """'+' if the repository exists
           'N' if the destination directory exists but isn't a git repo
           '-' if the destination doesn't exists"""
        if os.path.exists(os.path.join(local_url, self.metadata_dir)):
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


class Eg(SCM):
    name = "easygit"
    binary = "eg"
    def __init__(self):
        SCM.__init__(self)

eg = Eg()


class GitSvn(Git):
    """This Repository type replaces push/clone/pull with the git svn 
    commands dcommit/clone/rebase, here only hg is permitted"""
    aliases = {"push": "svn dcommit",
               "clone": "svn clone",
               "pull": "svn rebase"}

    name = "git-svn"

    def __init__(self, externals = [], headonly = False):
        Git.__init__(self)
        self.externals = externals
        self.headonly = headonly

    def __str_keyword_arguments__(self):
        return "(externals = %s, headonly = %s)" % (repr(self.externals), repr(self.headonly))

    def __externals(self, destdir):
        process = subprocess.Popen("cd %s; git svn propget svn:externals" % esc(destdir),
                                   shell = True,
                                   stderr = subprocess.PIPE,
                                   stdout = subprocess.PIPE)
        externals = [ re.split("\\s+", x.strip()) for x in process.stdout.readlines() 
                      if x != "\n" ]
        process.wait()

        return externals


    def execute(self, command, args, destdir = None):
        """Call execute for every external, if this command is in the externals attribute"""
        if command in dir(self):
            return getattr(self, command)(args = args, destdir = destdir)

        procs = Git.execute(self, command,args = args, destdir = destdir)

        if self.externals == True or command in self.externals:
            for [path, clone_url] in self.__externals(destdir):
                procs.extend( self.execute(command, args = args,
                                  destdir = os.path.join(destdir, path)))
        return procs

    def clone(self, args, destdir = None):
        # Append -r HEAD to command, so only the top commit is cloned
        if self.headonly:
            headonly = ['-r', 'HEAD']
        else:
            headonly = []

        destdir = args[1]
        procs = []
        # Call the actual git svn clone (with aliases!)
        procs.extend(self.bare_execute("clone", args = args + headonly))
        
        fd = open(os.path.join(destdir, ".git/info/exclude"), "a+")
        fd.write("\n# Metagit svn external excludes\n")
        
        if self.externals == True or "clone" in self.externals:
            for [path, clone_url] in self.__externals(destdir):
                local_url = os.path.join(destdir, path)
                fd.write(path + "/\n")
                # Call clone with other clone and local url
                procs.extend( self.execute("clone", args = [clone_url, local_url] + args[2:],
                                           destdir = local_url) )
        return procs

git_svn = gitsvn = GitSvn()
git_svn_externals = gitsvn_externals = GitSvn(externals = True)

class Mercurial(SCM):
    name = "hg"
    binary = "hg"
    metadata_dir = ".hg"
    def __init__(self):
        SCM.__init__(self)
mercurial = hg = Mercurial()
