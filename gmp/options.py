import optparse

class CommandHelpFormatter(optparse.IndentedHelpFormatter):
    """Just returns the epilog without reformatting"""
    def __init__(self, **kwargs):
        optparse.IndentedHelpFormatter.__init__(self, **kwargs)        

    def format_epilog(self, epilog):
        if not epilog:
            return ""
        return "\n" + epilog

class Options:
    """Helper class to store all command line options"""
    instance = None
    formatter=CommandHelpFormatter()

    def __init__(self, args, repo_manager):
        parser = optparse.OptionParser(usage = "usage: metagit [options] <command> [selector] -- [args]",
                                       epilog = repo_manager.generate_help())
        parser.add_option("-p", "--parallel", help = "run scm tasks in parallel",
                          action="store_true", default=False)
        parser.add_option("-s", "--screen", help = "run scm tasks in screen",
                          action="store_true", default=False)


        parser.formatter = self.formatter
        parser.formatter.set_parser(parser)

        self.parser = parser
        self.options, self.args = self.parser.parse_args(args)

    def parse(args, repo_manager):
        """Singleton getter with parse call"""
        if not Options.instance:
            Options.instance = Options(args, repo_manager)
        return Options.instance.args
    parse = staticmethod(parse)

    def opt(name):
        return getattr(Options.instance.options, name)
    opt = staticmethod(opt)
