import os
from socket import getfqdn
import re
import sys
import subprocess
import optparse

# Project specify
from gmp.policy import *
from gmp.repository import *
from gmp.listers import *
from gmp.tools import *
from gmp.scm import *
from gmp.options import *

#
# The Repository manager
#

class RepoManager:
    """Manages all repositories and provides the command line interface"""
    sets = {}

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
                         "diff" : self.shortcut("diff"),
                         "cd"    : self.cmd_cd,
                         "clean" : self.cmd_clean}

        # Translation table for short commands
        # FIXME: not documentated anywhere
        self.short_commands = {'c': 'clone'}

    def __call__(self):
        """The Reposity Manager can be called in order to start the command
line interface"""

        args = Options.parse(sys.argv[1:], self)
        if len(args) < 1:
            Options.instance.parser.print_help()
            return

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

    def generate_help(self, nroff = False):
        """Generate Command: section of --help"""
        
        if nroff:
            text = ".SH SELECTOR\n"
        else:
            text = "Selector:"
        
        text += """
  A selector is a regexp which is checked against the output of metagit
  list. (Exception: states (%s), current repository (.).

""" %(", ".join(SCM.states))

        # Find longest command
        length = max( [ len(x) for x in self.commands.keys() ] )
        if nroff:
            text += ".SH COMMANDS\n"
            format = ".TP\n.B\n%s\n%s\n"
        else:
            format = "  %" + str(length) + "s  %s\n"
            text += "Commands:\n"
        for cmd in sorted(self.commands.keys()):
            cmd_help = self.commands[cmd].__doc__.split("\n")
            text += format % (cmd, cmd_help[0])
            for line in cmd_help[1:]:
                if nroff:
                    text += line +"\n"
                else:
                    text += format %("", line)

        return text


    # use the die method from parser
    def die(self, msg):
        """Print message and die"""
        Options.instance.parser.error(msg)


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
                if selector == ".":
                    if os.path.exists(repo.local_url) and os.path.abspath(os.curdir).startswith(repo.local_url):
                        repos.append(repo)
                elif (selector == "all" or re.search(selector, repo.status_line())) \
                        and repo.check_policy(self.hostname):
                    if not state or repo.get_state() in state:
                        repos.append(repo)

        if selector == "." and len(repos) > 0:
            # Take the closest match
            repos = [sorted(repos, lambda a, b: len(b.local_url) - len(a.local_url))[0]]

        return repos
    
    def cmd_list(self, selector):
        """[selector] - lists only matching repos"""
        if len(selector) == 0:
            selector = ["all"]
        repos = self._select(selector[0])
        for repo in repos:
            print repo.status_line()
        
    def cmd_clone(self, selector):
        """[selector] - clones all matching repos"""
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
            help = "[selector] - executes <scm> %s on repositories" %(command,)
            func = lambda x: self.cmd_foreach([self._shortcut(x)[0], command] + self._shortcut(x)[1:])
        func.__doc__ = help
        return func

    def cmd_foreach(self, args):
        """<selector> <command>
executes `<scm> <command>' on matching repositories"""
        if len(args) < 2:
            self.die("Not enough arguments")
        repos = self._select(args[0])

        processes = []

        for repo in repos:
            if not repo.get_state() in [SCM.STATE_EXISTS, SCM.STATE_BARE]:
                continue
            # Give arguments to deeper layers and save the resulting processes
            process_list = repo.execute(args[1], args[2:])
            processes.extend(process_list)

        for p in processes:
            if p and "wait" in dir(p):
                p.wait()
        ScreenExecutor.execute()

    def cmd_clean(self, args):
        """deletes all repo lister cache files"""
        for lister in RepoLister.listers:
            if lister.cache:
                try:
                    os.unlink(lister.cache)
                except:
                    pass

    def cmd_cd(self, args):
        """[selector] - prints cd command to change to repository
If more then one repository is selected, a interactive dialog
will be shown to select from the matching ones"""
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
        """<RepoLister> <LocalRepo> <RemoteRepo>
Does upload an Repository to an remote site which is specified by an 
RepoLister name (e.g. an SSHDir)"""

        origin = False
        for o in ["-o", "--origin"]:
            if o in args:
                del args[args.index(o)]
                origin = True

        listers = filter(lambda x: x.can_upload(), RepoLister.listers)
        listers_name = map(lambda x: x.name, listers)

        if len(args) < 2 or not args[0] in listers_name:
            self.die("Available RepoListers: " + ", ".join(listers_name))
        
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

