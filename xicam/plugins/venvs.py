import pathlib

import sys, os
import venv
from appdirs import user_config_dir, site_config_dir, user_cache_dir
import subprocess
import platform
import os
import os.path
import pkgutil
import sys
import tempfile
import ensurepip

op_sys = platform.system()
if op_sys == 'Darwin':  # User config dir incompatible with venv on darwin (space in path name conflicts)
    user_venv_dir = os.path.join(user_cache_dir(appname='xicam'),'venvs')
else:
    user_venv_dir = os.path.join(user_config_dir(appname='xicam'),'venvs')
site_venv_dir = os.path.join(site_config_dir(appname='xicam'),'venvs')

venvs = {}
observers = []

# Python 2 style execfile function
execfile = lambda filename, globals=None, locals=None: exec(open(filename).read(), globals, locals)

# TODO: transition to http://virtualenvwrapper.readthedocs.io/en/latest/index.html

class EnvBuilder(venv.EnvBuilder):
    def _setup_pip(self, context):
        """ Override normal behavior using subprocess, call ensurepip directly"""
        self.bootstrap(root=os.path.dirname(os.path.dirname(context.env_exe)), upgrade=True, default_pip=True)

    @staticmethod
    def bootstrap(*, root=None, upgrade=False, user=False,
                  altinstall=False, default_pip=False,
                  verbosity=0):
        """
        Bootstrap modified from ensurepip to avoid issues with parent environment
        """
        if altinstall and default_pip:
            raise ValueError("Cannot use altinstall and default_pip together")

        ensurepip._disable_pip_configuration_settings()

        # By default, installing pip and setuptools installs all of the
        # following scripts (X.Y == running Python version):
        #
        #   pip, pipX, pipX.Y, easy_install, easy_install-X.Y
        #
        # pip 1.5+ allows ensurepip to request that some of those be left out
        if altinstall:
            # omit pip, pipX and easy_install
            os.environ["ENSUREPIP_OPTIONS"] = "altinstall"
        elif not default_pip:
            # omit pip and easy_install
            os.environ["ENSUREPIP_OPTIONS"] = "install"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Put our bundled wheels into a temporary directory and construct the
            # additional paths that need added to sys.path
            additional_paths = []
            for project, version in ensurepip._PROJECTS:
                wheel_name = "{}-{}-py2.py3-none-any.whl".format(project, version)
                whl = pkgutil.get_data(
                    "ensurepip",
                    "_bundled/{}".format(wheel_name),
                )
                with open(os.path.join(tmpdir, wheel_name), "wb") as fp:
                    fp.write(whl)

                additional_paths.append(os.path.join(tmpdir, wheel_name))

            # Construct the arguments to be passed to the pip command
            args = ["install", "--no-index", "--find-links", tmpdir]
            if root:
                args += ["--prefix", root] ######## Modified
            if upgrade:
                args += ["--upgrade"]
            if user:
                args += ["--user"]
            if verbosity:
                args += ["-" + "v" * verbosity]

            args += ['--ignore-installed'] ######## Added

            print('boostrap:', *(args + [p[0] for p in ensurepip._PROJECTS]))
            EnvBuilder._run_pip(args + [p[0] for p in ensurepip._PROJECTS], additional_paths)

    @staticmethod
    def _run_pip(args, additional_paths=None):
        oldpath=sys.path

        # Add our bundled software to the sys.path so we can import it
        if additional_paths is not None:
            sys.path = additional_paths + sys.path

        # Install the bundled software
        import pip
        try:
            pip.main(args)
        except AttributeError:
            from pip._internal import main
            main(args)

        # Restore sys.path
        sys.path=oldpath


def create_environment(name: str):
    """
    Create a new sandbox environment in the user_venv_dir with name name.

    Parameters
    ----------
    name : str
        Name of sandbox environment to create.
    """

    envpath = pathlib.Path(user_venv_dir, name)
    if envpath.is_dir():
        return
        # raise ValueError('Environment already exists.')
    EnvBuilder(with_pip=True).create(envpath)


def use_environment(name):
    """
    Activate the sandbox environment with name name in user_venv_dir

    Parameters
    ----------
    name : str
        Name of sandbox environment to activate
    """
    path = pathlib.Path(user_venv_dir, name)
    if not path.is_dir():
        raise ValueError(f"Sandbox environment '{name}' could not be found.")

    global current_environment
    current_environment = str(path)
    activate_this(current_environment)

    for observer in observers:
        observer.venvChanged()


def activate_this(path):
    # Below copied and modified from the activate_this.py module of virtualenv, which is missing form venv
    old_os_path = os.environ.get('PATH', '')
    os.environ['PATH'] = os.path.dirname(os.path.abspath(path)) + os.pathsep + old_os_path
    base = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    if sys.platform == 'win32':
        site_packages = os.path.join(base, 'Lib', 'site-packages')
    else:
        site_packages = os.path.join(base, 'lib', 'python%s' % sys.version[:3], 'site-packages')
    prev_sys_path = list(sys.path)
    # if not getattr(sys, 'frozen', False):  # site missing addsitedir when frozen
    try:
        import site
        addsitedir = site.addsitedir
    except AttributeError:  # frozen apps have no site-packages; and thus their site.py is fake
        # NOTE: relevant methods have been extracted from a real site.py
        def makepath(*paths):
            dir = os.path.join(*paths)
            try:
                dir = os.path.abspath(dir)
            except OSError:
                pass
            return dir, os.path.normcase(dir)
        def _init_pathinfo():
            """Return a set containing all existing file system items from sys.path."""
            d = set()
            for item in sys.path:
                try:
                    if os.path.exists(item):
                        _, itemcase = makepath(item)
                        d.add(itemcase)
                except TypeError:
                    continue
            return d

        def addpackage(sitedir, name, known_paths):
            """Process a .pth file within the site-packages directory:
               For each line in the file, either combine it with sitedir to a path
               and add that to known_paths, or execute it if it starts with 'import '.
            """
            if known_paths is None:
                known_paths = _init_pathinfo()
                reset = True
            else:
                reset = False
            fullname = os.path.join(sitedir, name)
            try:
                f = open(fullname, "r")
            except OSError:
                return
            with f:
                for n, line in enumerate(f):
                    if line.startswith("#"):
                        continue
                    try:
                        if line.startswith(("import ", "import\t")):
                            exec(line)
                            continue
                        line = line.rstrip()
                        dir, dircase = makepath(sitedir, line)
                        if not dircase in known_paths and os.path.exists(dir):
                            sys.path.append(dir)
                            known_paths.add(dircase)
                    except Exception:
                        print("Error processing line {:d} of {}:\n".format(n + 1, fullname),
                              file=sys.stderr)
                        import traceback
                        for record in traceback.format_exception(*sys.exc_info()):
                            for line in record.splitlines():
                                print('  ' + line, file=sys.stderr)
                        print("\nRemainder of file ignored", file=sys.stderr)
                        break
            if reset:
                known_paths = None
            return known_paths
        def addsitedir(sitedir, known_paths=None):
            """Add 'sitedir' argument to sys.path if missing and handle .pth files in
            'sitedir'"""
            if known_paths is None:
                known_paths = _init_pathinfo()
                reset = True
            else:
                reset = False
            sitedir, sitedircase = makepath(sitedir)
            if not sitedircase in known_paths:
                sys.path.append(sitedir)  # Add path component
                known_paths.add(sitedircase)
            try:
                names = os.listdir(sitedir)
            except OSError:
                return
            names = [name for name in names if name.endswith(".pth")]
            for name in sorted(names):
                addpackage(sitedir, name, known_paths)
            if reset:
                known_paths = None
            return known_paths

    addsitedir(site_packages)

    sys.real_prefix = sys.prefix
    sys.prefix = base
    # Move the added items to the front of the path:
    new_sys_path = []
    for item in list(sys.path):
        if item not in prev_sys_path:
            new_sys_path.append(item)
            sys.path.remove(item)
    sys.path[:0] = new_sys_path


current_environment = ''

# TODO: find all venvs; populate the venvs global
def initialize_venv():
    global current_environment
    create_environment("default")
    use_environment("default")
    current_environment = str(pathlib.Path(user_venv_dir, "default"))
