def esc(str):
    return str.replace("'", "\\'")

class Options:
    """Helper class to store all command line options"""
    options = []
    def get(keys):
        """see if command line option is set"""
        for opt, val in Options.options:
            if opt in keys:
                return val
    get = staticmethod(get)
