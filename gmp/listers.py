import os, sys
import urllib2, urllib
import re
import subprocess
import json
from xml.dom.minidom import parse as xml_parse

from gmp.policy import *
from gmp.repository import *
from gmp.tools import *
#
# Repository Lister Services
#

class RepoLister (PolicyMixin):
    listers = []

    def __init__(self, cache = None, default_policy = "allow", scm = Git(), name = None, 
                 into = "~/", **kwargs):
        PolicyMixin.__init__(self, default_policy)

        RepoLister.listers.append(self)
        
        if cache:
            self.cache = os.path.expanduser(cache)
        else:
            self.cache = None

        self.clone_urls = None
        self.local_directory = into

        # Default source control management is git, but can be changed by more specific listers
        self.scm = scm

        # Save all the other arguments, they will be pushed to repository constructors
        self.kwargs = kwargs

        self.name = name

    def urls(self):
        """Retures a list of clone urls in the SSHDir"""
        if self.clone_urls is None:
            self.get_list()
        return self.clone_urls

    def get_list(self):
        pass

    def create_repos(self):
        repos = []
        for url in self.urls():
            if type(url) in [tuple, list]:
                repos.append( Repository(url[0], os.path.join(self.local_directory, url[1]), scm = self.scm, **self.kwargs))
            else:
                repos.append( Repository(url, into = self.local_directory, scm = self.scm, **self.kwargs))
        return repos

    def __iter__(self):
        # Check Policy against own FQDN
        if not self.check_policy():
            return [].__iter__()

        if self.cache:
            # There may be a Repository Cache
            if os.path.exists(self.cache):
                try:
                    cache = open(self.cache)
                    repos = eval(cache.read())
                    cache.close()
                    return repos.__iter__()
                except Exception, e:
                    print "WARNING: Invalid cache file: " + self.cache
                    # Disabling Cache
                    self.cache = None
                    print e
            
        # Cache does not exist try to build it
        repos = self.create_repos()
        if self.cache and len (repos) > 0:
            cache = open(self.cache, "w+")
            cache.write("[%s" % str(repos[0]))
            for r in repos[1:]:
                cache.write(",\n %s" % str(r))
            cache.write("]")
            cache.close()
        return repos.__iter__()

    def can_upload(self):
        """Returns True if the Repository Lister is able to move a repository from local to this site
If it returns True, it must have an attribute name and a method upload(self, local_url, remote_url)"""
        return False

class SSHDir(RepoLister):
    """With you can create SSHDir a list of git repositories on an remote host"""

    def __init__(self, host, directory, **kwargs):
        """host: ssh login used with ssh
directory: remote directory where the git repos are searched"""
        RepoLister.__init__(self, **kwargs)
        self.host = host
        self.directory = directory

        if not self.name:
            self.name = host


    def get_list(self):
        process = subprocess.Popen(["ssh", self.host, "find", self.directory, 
                                    "-maxdepth", "4", "-type", "d"], 
                                   stdout = subprocess.PIPE,
                                   stderr = subprocess.PIPE)
        process.stderr.close()
        self.clone_urls = []
        for repo in process.stdout.readlines():
            # Finding none bare repositories
            m = re.match("^(.*)/\.%s$" % self.scm.binary, repo)
            m = m or re.match("(.*)/refs$", repo)
            if m and not re.match(".*(svn|logs)/refs", repo) and not re.match(".*\.%s/" % self.scm.binary, repo):
                remote = m.group(1)
                local = remote[len(self.directory)+1:]
                self.clone_urls.append((self.host + ":" + remote, local))
                
    def can_upload(self):
        """You can upload a repository to a remote site"""
        return True

    def upload(self, local, remote):
        """Uploads a local repository with scp to a remote location"""

        push_url = "%s:%s" %(self.host,
                             os.path.join(self.directory, remote))
        
        cmd = "scp -r %s %s"% (esc(local),
                               esc(push_url))
        print cmd
        a = subprocess.Popen(cmd, shell = True)
        a.wait()
        os.unlink(self.cache)

        return Repository(push_url, local, default_policy = self.default_policy, scm = self.scm)
        

class Gitolite(RepoLister):
    """With this you can work against a Gitolite server on a remote host"""

    def __init__(self, host, **kwargs):
        """host: server where gitolite is running"""
        if not 'scm' in kwargs:
            kwargs['scm'] = Git()
        RepoLister.__init__(self, **kwargs)
        self.host = host

    def get_list(self):
        process = subprocess.Popen(["ssh", self.host, "expand"],
                                   stdout = subprocess.PIPE)

        self.clone_urls = []
        for repo in process.stdout.readlines():
            repo = repo.strip()
            #     &R_ &W_	<gitolite>	nosmd
            m = re.match("^.*\t(.*)$", repo)

            if m:
                self.clone_urls.append((self.host + ":" + m.group(1) + ".git", m.group(1)))

    def can_upload(self):
        """You can push a local repository to a gitolite server"""
        return True

    def upload(self, local, remote):
        """Pushes a local repository to a gitolite server"""

        print "TODO: Need to setup initial config for pushing to gitolite and then push"
        sys.exit(-1)


class Github(RepoLister):
    def __init__(self, username = None, protocol="ssh", wiki = False, **kwargs):
        """Uses a github account name to get a list of repositories
username: github.com username (can be derived from github.user)
protocol: used for cloning the repository (choices: ssh/https/git)"""
        # GIThub!!!!
        kwargs['scm'] = Git()
        if not 'name' in kwargs or not kwargs['name']:
            kwargs['name'] = "github"

        self.wiki = wiki
        if type(wiki) != type(""):
            self.wiki = "wiki"
        
        RepoLister.__init__(self, **kwargs)
        self.username = username
        if self.username == None:
            cmd = "git config --get github.user"
            process = subprocess.Popen(cmd, shell = True,
                                       stdout = subprocess.PIPE,
                                       stderr = subprocess.PIPE)
            process.stderr.close()
            username = process.stdout.readline().strip()
            if username == "":
                print """ERROR: No username defined for Github lister, please define github.user
    via git config or put it into the config file"""
                sys.exit(-1)
            self.username = username
            
        self.protocol = protocol

    def get_list(self):
        js = urllib2.urlopen("https://api.github.com/users/%s/repos"%self.username).read()
        repos = json.loads(js)
        self.clone_urls = []
        for repo in repos:
            name = repo["name"]
            wiki = repo["has_wiki"]
            self.clone_urls.append(self.github_url(name))
            if self.wiki and wiki:
                self.clone_urls.append((self.github_url(name + ".wiki"), name + "/" + self.wiki))

    def github_url(self, name):
        url = ""
        if self.protocol == "ssh":
            url = "git@github.com:%s/%s.git" % (self.username, name)
        elif self.protocol == "https":
            url = "https://%s@github.com/%s/%s.git" %(self.username, self.username, name)
        else:
            url = "git://github.com/%s/%s.git" %(self.username, name)
        return url
        
    def can_upload(self):
        """You can upload a repository to a remote site"""
        return True

    def upload(self, local, remote):
        """Creates a new repository at github and pushes the local one to it.
Please set the github.token variable via git config"""
        cmd = "git config --get github.token"
        print cmd
        process = subprocess.Popen(cmd, shell = True,
                                   stdout = subprocess.PIPE,
                                   stderr = subprocess.PIPE)
        process.stderr.close()
        token = process.stdout.readline().strip()
        if token == "":
            print "ERROR: Please define github.token via git config"
            sys.exit(-1)

        print "Creating new remote repository '%s'" % remote
        data = urllib.urlencode({'login': self.username, 'token': token, 'name': remote})
        try:
            xml = urllib2.urlopen("http://github.com/api/v2/xml/repos/create", data = data)
        except:
            print "ERROR: Wrong token or repository already exists"
            sys.exit(-1)
        xml.close()

        cmd = "cd %s; git push %s master" % (esc(local),
                                             esc(self.github_url(remote)))
        print cmd
        a = subprocess.Popen(cmd, shell = True)
        a.wait()
        os.unlink(self.cache)

        return Repository(self.github_url(remote), remote, default_policy = self.default_policy, scm = 'git')


class SVNList(RepoLister):
    def __init__(self, svn_repo, postfix = "", **kwargs):
        """Uses a svn list to get a list of svn repositories, which can be used as SVNRepository's
svn_repo: e.g svn+ssh://stettberger@barfoo.com/admin
postfix: e.g trunk, will be appended to the clone url"""
        # This works just with git svn!
        if not 'scm' in kwargs:
            kwargs['scm'] = GitSvn()
        RepoLister.__init__(self, **kwargs)
        self.svn_repo = svn_repo
        self.postfix = postfix

    def get_list(self):
        process = subprocess.Popen(["svn", "list", self.svn_repo], 
                                   stdout = subprocess.PIPE)

        self.clone_urls = []
        for repo in process.stdout.readlines():
            repo = repo.strip()
            self.clone_urls.append((os.path.join(os.path.join(self.svn_repo, repo), self.postfix), repo))

class Gitorious(RepoLister):
    def __init__(self, username, protocol="ssh", gitorious="gitorious.org", **kwargs):
        """Uses a gitorous account name to get a list of repositories
username: gitorous username
protocol: used for cloning the repository (choices: ssh/http/git)"""
        # GITorious!!!
        kwargs['scm'] = Git()
        RepoLister.__init__(self, **kwargs)

        self.username = username
        self.protocol = protocol
        self.gitorious = gitorious

    def get_list(self):
        print "http://%s/~%s"%(self.gitorious, self.username)
        site = urllib2.urlopen("https://%s/~%s"%(self.gitorious, self.username))
        lines_to_read = 0

        self.clone_urls = []
        prefixes = {"ssh": "git@%s:"%self.gitorious,
                    "http": "git.%s/"%self.gitorious,
                    "git": "git://%s/"%self.gitorious}

        if not self.protocol in prefixes:
            print "Protocol %s not supported by gitorious list plugin" % self.protocol
            sys.exit(-1)

        # FIXME: Find a good API for gitorious cause this frickel
        # might fail in the future, if gitorious starts to send sane
        # html

        for line in site.readlines():
            if re.match('.*class="repository"', line):
                lines_to_read = 2
            if lines_to_read > 0:
                m = re.match('.*href="/([^"]*)"', line)
                if m:
                    self.clone_urls.append(prefixes[self.protocol] + m.group(1) + ".git")
                lines_to_read -= 1

class Gitlab(RepoLister):
    def __init__(self, host = None, **kwargs):
        """Uses a gitlab account name to get a list of repositories
username: gitl username (can be derived from github.user)
protocol: used for cloning the repository (choices: ssh/https/git)"""
        # GIThub!!!!
        kwargs['scm'] = Git()
        if not 'name' in kwargs or not kwargs['name']:
            kwargs['name'] = "gitlab"

        RepoLister.__init__(self, **kwargs)
        cmd = "git config --get gitlab.%s.token" % host
        process = subprocess.Popen(cmd, shell = True,
                                   stdout = subprocess.PIPE,
                                   stderr = subprocess.PIPE)
        process.stderr.close()
        token = process.stdout.readline().strip()
        if token == "":
            print """ERROR: No gitlab token defined. Please define gitlab.token defined for Github lister, please define github.user
            via git config or put it into the config file"""
            sys.exit(-1)

        self.gitlab_token = token
        self.host = host

    def get_list(self):
        headers = {"PRIVATE-TOKEN": self.gitlab_token}
        url = "https://%s/api/v3/projects/owned" % self.host
        request = urllib2.Request(url, headers=headers)
        js = urllib2.urlopen(request).read()
        repos = json.loads(js)
        self.clone_urls = []
        for repo in repos:
            name = repo["name"]
            ssh_url = repo["ssh_url_to_repo"]
            self.clone_urls.append((ssh_url, name))
