#!/usr/bin/python

from gmp.main import *
import datetime
import optparse
from distutils.command.build import build
from distutils.core import Command

class ManPageFormatter(optparse.HelpFormatter):
    def __init__(self, indent_increment=2, max_help_position=24,
                 width=None, short_first=1):
        """CONSTRUCTOR. UNFORTUNATELY HELPFORMATTER IS NO NEW-STYLE CLASS."""
        optparse.HelpFormatter.__init__(self, indent_increment,
                                        max_help_position, width, short_first)
        
    def _markup(self, txt):
        """PREPARES TXT TO BE USED IN MAN PAGES."""
        return txt.replace('-', '\\-')
    
    def format_usage(self, usage):
        """FORMATE THE USAGE/SYNOPSIS LINE."""
        return self._markup(usage)
 
    def format_heading(self, heading):
        """FORMAT A HEADING.
        IF LEVEL IS 0 RETURN AN EMPTY STRING. THIS USUALLY IS THE STRING "OPTIONS".
        """
        if self.level == 0:
            return ''
        return '.TP\n%s\n' % self._markup(heading.upper())
 
    def format_option(self, option):
        """FORMAT A SINGLE OPTION.
        THE BASE CLASS TAKES CARE TO REPLACE CUSTOM OPTPARSE VALUES.
        """
        result = []
        opts = self.option_strings[option]
        result.append('.TP\n.B\n%s\n' % self._markup(opts))
        if option.help:
            help_text = '%s\n' % self._markup(self.expand_default(option))
            result.append(help_text)
        return ''.join(result)

class build_manpage(Command):
    description = 'Generate man page'
    user_options = []
    def initialize_options(self):
        Options.formatter = f = ManPageFormatter()
        self.repo = RepoManager()
        Options.parse([], self.repo)
        self.parser = Options.instance.parser

    def finalize_options(self):
        pass

    def run(self):
        stream = open(self.distribution.get_name()+".1", 'w+')
        self._write_header(stream)

    def _write_header(self, stream):
        appname = self.distribution.get_name()
        desc = self.distribution.get_description()
        m = self.parser.formatter._markup
        stream.write(".TH %s 1 %s\n" %  (m(appname), datetime.datetime.today().strftime("%Y\\-%m\\-%d")))
        stream.write(".SH NAME\n%s - %s\n" %(m(appname), m(desc)))
        stream.write(".SH SYNPOSIS\n%s\n" % self.parser.get_usage())
        stream.write(".SH DESCRIPTION\n%s\n" % m(self.distribution.get_long_description()))
        stream.write(".SH OPTIONS\n%s\n" % self.parser.format_option_help())
        stream.write(self.repo.generate_help(nroff=True) + "\n")

        stream.write(""".SH ENVIRON
.TP
.B
METAGITRC
use another config file instead of ~/.metagitrc
""")
        author = '%s <%s>' % (self.distribution.get_author(),
                              self.distribution.get_author_email())
        stream.write('.SH AUTHORS\n.B %s\nwas written by %s.\n'
                    % (m(appname), m(author)))
        homepage = self.distribution.get_url()
        stream.write('.SH DISTRIBUTION\nThe latest version of %s may '
                    'be downloaded from\n'
                    '.UR %s\n.UE\n'
                     % (m(appname), m(homepage),))

build.sub_commands.append(('build_manpage', None))





