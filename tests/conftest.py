
import os
import pwd
import grp
import collections
from pathlib import Path

import pytest
from _pytest.pytester import LineMatcher
from textwrap import dedent
import mailadm.config


@pytest.fixture(autouse=True)
def _nocfg(monkeypatch):
    monkeypatch.delenv("MAILADM_CFG", raising=False)

    cfg = os.path.expanduser("~mailadm") + os.sep + "mailadm.cfg"

    def exists(path, _exists=os.path.exists):
        if path == cfg:
            return False
        return _exists(path)

    monkeypatch.setattr(os.path, "exists", exists)


class ClickRunner:
    def __init__(self, main):
        from click.testing import CliRunner
        self.runner = CliRunner()
        self._main = main
        self._rootargs = []

    def set_basedir(self, account_dir):
        self._rootargs.insert(0, "--basedir")
        self._rootargs.insert(1, account_dir)

    def run_ok(self, args, fnl=None, input=None):
        __tracebackhide__ = True
        argv = self._rootargs + args
        # we use our nextbackup helper to cache account creation
        # unless --no-test-cache is specified
        res = self.runner.invoke(self._main, argv, catch_exceptions=False,
                                 input=input)
        if res.exit_code != 0:
            print(res.output)
            raise Exception("cmd exited with %d: %s" % (res.exit_code, argv))
        return _perform_match(res.output, fnl)

    def run_fail(self, args, fnl=None, input=None, code=None):
        __tracebackhide__ = True
        argv = self._rootargs + args
        res = self.runner.invoke(self._main, argv, catch_exceptions=False,
                                 input=input)
        if res.exit_code == 0 or (code is not None and res.exit_code != code):
            print(res.output)
            raise Exception("got exit code {!r}, expected {!r}, output: {}".format(
                res.exit_code, code, res.output))
        return _perform_match(res.output, fnl)


def _perform_match(output, fnl):
    __tracebackhide__ = True
    if fnl:
        lm = LineMatcher(output.splitlines())
        lines = [x.strip() for x in fnl.strip().splitlines()]
        try:
            lm.fnmatch_lines(lines)
        except Exception:
            print(output)
            raise
    return output


@pytest.fixture
def cmd():
    """ invoke a command line subcommand. """
    from mailadm.cmdline import mailadm_main
    return ClickRunner(mailadm_main)


@pytest.fixture
def config(tmpdir, make_config):
    path = tmpdir.ensure("base", dir=1)
    return make_config(path)


@pytest.fixture
def make_config(monkeypatch):
    def make_config(basedir):
        path = basedir.ensure("paths", dir=1)
        path_mailadm_db = path.join("mailadm.db")
        mail_domain = "testrun.org"
        web_endpoint = "https://testrun.org/new_email"
        path_virtual_mailboxes = path.ensure("path_virtual_mailboxes")
        source = dedent("""
            [sysconfig]
            path_mailadm_db= {path_mailadm_db}
            mail_domain = {mail_domain}
            web_endpoint = {web_endpoint}
            path_virtual_mailboxes = {path_virtual_mailboxes}
            vmail_user = vmail
        """.format(**locals()))

        p = basedir.join("mailadm.cfg")
        p.write(source)

        ttype = collections.namedtuple("pwentry", ["pw_name", "pw_dir", "pw_uid", "pw_gid"])

        def getpwnam(name):
            if name == "vmail":
                p = Path(path.ensure("path_vmaildir", dir=1).strpath)
            elif name == "mailadm":
                p = Path(path.ensure("path_mailadm_home", dir=1).strpath)
            else:
                raise KeyError("don't know user {!r}".format(name))
            return ttype(name, p, 10000, 10000)  # uid/gid should play no role for testing
        monkeypatch.setattr(pwd, "getpwnam", getpwnam)

        gtype = collections.namedtuple("grpentry", ["gr_name", "gr_mem"])

        def getgrnam(name):
            if name == "vmail":
                gr_mem = ["mailadm"]
            else:
                gr_mem = []
            return gtype(name, gr_mem)
        monkeypatch.setattr(grp, "getgrnam", getgrnam)

        return mailadm.config.Config(str(p))

    return make_config
