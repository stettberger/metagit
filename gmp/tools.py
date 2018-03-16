from gmp.options import *
import subprocess
import tempfile
import os

class ScreenExecutor:
    instance = None
    def __init__(self):
        self.screen_fd, self.screen_path = tempfile.mkstemp()
        self.counter = 0
        self.screen_fd = os.fdopen(self.screen_fd, "w")

    def get():
        if not ScreenExecutor.instance:
            ScreenExecutor.instance = ScreenExecutor()
        return ScreenExecutor.instance
    get = staticmethod(get)

    def push(cmd):
        i = ScreenExecutor.get()
        i.screen_fd.write("""screen %d sh -c "echo; echo '%s' ; %s; echo Press ENTER;read a"\n"""
                          % (i.counter, cmd.replace("'", "\\\""), cmd))
        i.counter += 1
    push = staticmethod(push)

    def execute():
        if Options.opt('screen'):
            i = ScreenExecutor.get()
            i.screen_fd.write('caption always "%{wR}%c | %?%-Lw%?%{wB}%n*%f %t%?(%u)%?%{wR}%?%+Lw%?"\n')
            i.screen_fd.close()
            a = subprocess.Popen("screen -c %s" % i.screen_path, shell=True)
            a.wait()

            os.unlink(i.screen_path)
    execute = staticmethod(execute)


def esc(str):
    str = str.replace("\\", "\\\\")
    quote = False
    for c in " ;&|{}()$":
        if c in str:
            quote = True
    if quote:
        return "'" + str.replace("'", "\\'") + "'"
    return str

echo_exec = True
def execute(cmd, echo=True):
    if Options.opt('screen'):
        ScreenExecutor.push(cmd)
        return

    if echo:
        print(cmd)
    a = subprocess.Popen(cmd, shell=(type(cmd) == str))

    # Just wait here if we are not in parallel mode
    if not Options.opt('parallel'):
        a.wait()
    return a
