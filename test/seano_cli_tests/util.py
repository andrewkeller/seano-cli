# util.py
#
# Shared test helpers
import os
import shutil
import stat
import sys


def rmrf(workdir):
    def on_error(func, path, exc_info): #pylint: disable=W0613
        """
        Error handler for ``shutil.rmtree``.

        Stolen from <https://stackoverflow.com/questions/2656322/shutil-rmtree-fails-on-windows-with-access-is-denied>

        In particular on Windows, if the error is due to an access error (read only file),
        attempt to add write permission and then retry.  This is useful in particular with
        Git repositories, where files on disk in the objects database are marked as read-only,
        which makes the default invocation of ``shutil.rmtree`` grumpy.

        If the error is for another reason, we do not handle the error (re-raise it).
        """
        if not os.access(path, os.W_OK): # Is the error an access error?
            os.chmod(path, stat.S_IWUSR)
            func(path)
            return
        raise #pylint: disable=E0704

    if sys.platform not in ['win32']:
        # Trying to keep overall behavior as close to "normal" as possible.  Fewer hacks is better?
        on_error = None
    shutil.rmtree(workdir, onerror=on_error)
