import os
from socket import getfqdn
import re
import sys
import subprocess


# Project specify
from policy import *
from repository import *
from listers import *
from tools import *
from scm import *


#
# The Repository manager
#

class RepoManager:
    """Manages all repositories and provides the command line interface"""
    sets = {}
    help_commands = {"selector": """A selector is a regexp which is checked against the output of 
metagit list. (Exception: the states (%s) will filter the corresponding repos)""" %(", ".join(SCM.states))}

    def __init__(self):
        self.hostname = getfqdn()
        self.commands = {"list": self.cmd_list,
                         "clone": self.cmd_clone,
                         "upload": self.cmd_upload,
                         "foreach": self.cmd_foreach,
                         "status" : self.shortcut("status"),
                         "commit" : self.shortcut("commit"),
                         "push" : self.shortcut("push"),
                         "pull" : self.shortcut("pull"),
                         "fetch" : self.shortcut("fetch"),
                         "sets"  : self.cmd_sets,
                         "cd"    : self.cmd_cd,
                         "clean" : self.cmd_clean,
                         "help" : self.cmd_help}

        # Translation table for short commands
        # FIXME: not documentated anywhere
        self.short_commands = {'c': 'clone'}

    def __call__(self):
        """The Reposity Manager can be called in order to start the command
line interface"""
        args = sys.argv[1:]
        if len(args) < 1:
            self.die("Too less arguments")


        # Use prefixing to do short commands
        short = [x for x in self.commands.keys() if x.startswith(args[0])]
        if len(short) == 1:
            self.commands[short[0]](args[1:])
        elif args[0] in self.short_commands:
            self.commands[self.short_commands[args[0]]](args[1:])
        elif len(short) > 1:
            self.die("Unsure commands, possible: " + ", ".join(short))
        else:
            self.die("Command not found: " + args[0])

    def die(self, msg):
        print msg
        print
        print "For more Info: metagit help <something>"
        print "  `metagit help all' for help to everything"
        print
        print "Commands: " + ", ".join(self.commands.keys())
        print "Topics: " + ", ".join(self.help_commands.keys())
        
        sys.exit(-1)


    def add_set(self, set_name, repo_list):
        """You can add a list of repositories to a set"""
        # Make it possible to use add_set without a list
        if not isinstance(repo_list, (list,tuple, RepoLister)):
            repo_list = [repo_list]

        if not set_name in self.sets:
            self.sets[set_name] = []

        for repo in list(repo_list):
            repo.set.append(set_name)
            self.sets[set_name].append(repo)

    def _select(self, selector, state = None):
        # If the selector is a state, it will be searched only at the beginning
        if selector in SCM.states:
            selector = "^\\" + selector
        repos = []
        for s in self.sets.keys():
            for repo in self.sets[s]:
                if os.path.exists(repo.local_url) \
                   and os.path.exists(selector) \
                   and os.path.samefile(selector, repo.local_url):
                    print repo.local_url
                    return [repo]
                if (selector == "all" or re.search(selector, repo.status_line())) \
                        and repo.check_policy(self.hostname):
                    if not state or repo.get_state() in state:
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
            print repo.status_line()
        
    def cmd_clone(self, selector):
        """metagit clone [selector]
clone all repositories available on this host, if no selector given, clone all"""
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
                repo.execute("clone", [repo.clone_url, repo.local_url])

    def _shortcut(self, args):
        if len(args) == 0:
            return ["all"]
        return args

    def shortcut(self, command, help = None):
        if not help:
            help = "alias %s <selector> = foreach <selector> %s" %(command, command)
        func = lambda x: self.cmd_foreach([self._shortcut(x)[0], command] + self._shortcut(x)[1:])
        func.__doc__ = help
        return func

    def cmd_foreach(self, args):
        """metagit foreach <selector> <command>
executes command on all repositories matching the selector

`help selector' for more information on selectors"""
        if len(args) < 2:
            self.die("Not enough arguments")
        repos = self._select(args[0])
        for repo in repos:
            if not repo.get_state() in [SCM.STATE_EXISTS, SCM.STATE_BARE]:
                continue
            repo.execute(args[1], args[2:])

    def cmd_sets (self, args):
        """metagit sets [regex]
Prints a detailed overview on the sets which matches the [regex] or all"""
        if len(args) < 1:
            args = ["all"]

        for key in self.sets.keys():
            if args[0] == "all" or re.search(args[0], key):
                print "%s:" % key
                for repo in self.sets[key]:
                    print "  " + repo.status_line()

    def cmd_clean(self, args):
        """Deletes all cache files used by RepoListers"""
        for lister in RepoLister.listers:
            if lister.cache:
                try:
                    os.unlink(lister.cache)
                except:
                    pass

    def cmd_cd(self, args):
        """Prints a cd commando, which, after executed jumps to the repo
For direct use in the shell use this command:

function mm() {
   $(metagit cd $@)
}"""
        if len(args) == 0:
            print "echo Please specify target repository"
            return
        repos = self._select(args[0], state = [SCM.STATE_EXISTS, SCM.STATE_BARE])
        if len(repos)  == 1:
            print "cd " + esc(repos[0].local_url)
        elif len(repos) > 1:
            for r in range(1, len(repos)+1):
                sys.stderr.write("%d. %s\n" %(r,repos[r-1].local_url))


            sys.stderr.write("\nSelect Repository: ")
            try:
                select = input()
            except:
                return
            if select <= len(repos):
                print "cd " + esc(repos[select - 1].local_url)
            else:
                print "echo Selection out of range"
        else:
            print "echo No correspongding repository found"


    def cmd_upload(self, args):
        """metagit upload <RepoLister> <LocalRepo> [RemoteRepo]

Does upload an Repository to an remote site which is specified by an 
RepoLister name (e.g. an SSHDir)
        
--origin | -o: set the origin remote to this new repository.
"""

        origin = False
        for o in ["-o", "--origin"]:
            if o in args:
                del args[args.index(o)]
                origin = True

        listers = filter(lambda x: x.can_upload(), RepoLister.listers)
        listers_name = map(lambda x: x.name, listers)

        if len(args) < 2 or not args[0] in listers_name:
            self.cmd_help(["upload"])
            print
            print "Available RepoListers: " + ", ".join(listers_name)
            return
        
        # Find the matching repo lister to the name
        lister = listers[listers_name.index(args[0])] 
        local_url = args[1]
        if not os.path.exists(local_url):
            print "Local Repository doesn't exist"
            sys.exit(-1)

        if len(args) < 3:
            remote_url = args[1].split("/")[-1]
        else:
            remote_url = args[2]

        print "Uploading '%s' to '%s' on %s" %(local_url, remote_url, lister.name)
        sys.stdout.write("Proceed? (Y/n) ")
        a = raw_input()
        if a in ["", "y", "Y", "yes"]:
            repo = lister.upload(local_url, remote_url)
        else:
            print "Aborting."
            sys.exit(-1)

        # Changing the origin remote
        if origin:
            cmd = "cd '%s'; git remote rm origin; git remote add origin '%s'" \
                  %(esc(repo.local_url), esc(repo.clone_url))
            print cmd
            a = subprocess.Popen(cmd, shell = True)
            a.wait()

    def cmd_help(self, args):
        """recursive: see recursive"""
        if len(args) < 1:
            self.die("No topic selected")
        if args[0] == "all":
            topics = self.commands.keys() + self.help_commands.keys()
            for t in sorted(topics):
                self.cmd_help([t])
                print
        elif args[0] in self.commands:
            doc = self.commands[args[0]].__doc__
            if doc:
                sys.stdout.write(args[0] + ":")
                print re.sub("(^|\n)", "\n  ", doc)
            else:
                self.die("No help available")

        elif args[0] in self.help_commands:
            sys.stdout.write(args[0] + ":")
            print re.sub("(^|\n)", "\n  ", self.help_commands[args[0]])

        else:
            self.die("No help available")
