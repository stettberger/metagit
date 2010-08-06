import os
import urllib2
import re
import subprocess
from xml.dom.minidom import parse as xml_parse

from policy import *
from repository import *
#
# Repository Lister Services
#

class RepoLister (PolicyMixin):
    listers = []

    def __init__(self, cache = None):
        PolicyMixin.__init__(self, "allow")

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

    def create_repos(self):
        return [Repository(url, into = self.local_directory) for url in self.urls()]

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
                except:
                    print "WARNING: Invalid cache file: " + self.cache
                    # Disabling Cache
                    self.cache = None
            
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
                                    "-maxdepth", "2", "-type", "d"], 
                                   stdout = subprocess.PIPE,
                                   stderr = subprocess.PIPE)
        process.stderr.close()
        self.clone_urls = []
        for repo in process.stdout.readlines():
            # Finding none bare repositories
            m = re.match("(.*)/\.git", repo)
            if m:
                self.clone_urls.append(self.host + ":" + m.group(1))
            # Finding bare repositories
            m = re.match("(.*)/refs", repo)
            if m:
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

class SVNList(RepoLister):
    def __init__(self, svn_repo, postfix = "", cache = None):
        """Uses a svn list to get a list of svn repositories, which can be used as SVNRepository's
svn_repo: e.g svn+ssh://stettberger@barfoo.com/admin
postfix: e.g trunk, will be appended to the clone url"""
        RepoLister.__init__(self, cache)
        self.svn_repo = svn_repo
        self.postfix = postfix

    def create_repos(self):
        return [SVNRepository(url, into = self.local_directory, repo_name = repo) for (repo, url) in self.urls()]


    def get_list(self):
        process = subprocess.Popen(["svn", "list", self.svn_repo], 
                                   stdout = subprocess.PIPE)

        self.clone_urls = []
        for repo in process.stdout.readlines():
            repo = repo.replace("/\n", "")
            self.clone_urls.append((repo, os.path.join(os.path.join(self.svn_repo, repo), self.postfix)))

class Gitorious(RepoLister):
    def __init__(self, username, protocol="ssh", cache = None, gitorious="gitorious.com"):
        """Uses a gitorous account name to get a list of repositories
username: gitorous username
protocol: used for cloning the repository (choices: ssh/http/git)"""
        RepoLister.__init__(self, cache)

        self.username = username
        self.protocol = protocol
        self.gitorious = gitorious

    def get_list(self):
        site = urllib2.urlopen("http://%s/~%s"%(self.gitorious, self.username))
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

        
                     
        
