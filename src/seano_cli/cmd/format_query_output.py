"""
seano_cli/cmd/format_query_output.py

Interactive command-line wrapper on top of the infrastructure that converts a seano query output file into
a human-readable format.
"""

from seano_cli.utils import SeanoFatalError
import importlib
import logging
import pkgutil
import re
import sys

log = logging.getLogger(__name__)

PUBLIC_FORMATTER_MODULE_NAME_PREFIX = 'seano_formatter_'


def list_public_formatters():
    def iter():
        pattern = '^' + re.escape(PUBLIC_FORMATTER_MODULE_NAME_PREFIX) + '(?P<name>.*)$'
        log.debug('Searching for installed Python modules matching the regex /%s/', pattern)
        pattern = re.compile(pattern)
        for _, name, _ in pkgutil.iter_modules():
            m = pattern.match(name)
            if m:
                yield m.group('name')
    return sorted(iter())


def format_query_output(format_name, args, usage_str='<utest>', list_formatters=False):
    if list_formatters:
        pfs = list_public_formatters()
        if pfs:
            for name in pfs:
                print(name)
            return
        sys.stderr.write('No Seano formatter plugins are advertising their existence on this system, however you may still be able to invoke private formatters if you know their fully qualified Python module name.\n')
        return

    if not isinstance(format_name, str):
        pfs = list_public_formatters()
        if pfs:
            epilog = ['The available formats on this system are:'] + ['  %s' % (x,) for x in pfs]
        else:
            epilog = ['No Seano formatter plugins are advertising their existence on this system.']
        epilog = epilog + [
            '',
            'To use a private formatter that is not packaged as a public',
            'Seano Formatter plugin, specify its fully qualified Python',
            'module name, such as `my_pkg.my_module:my_func`.  The function',
            'name can be dropped if it is exactly equal to `format_<name>`,',
            'where <name> is the inner-most module name.',
        ]
        raise SeanoFatalError('\n'.join([usage_str] + epilog))
        return

    def interpret_format_name():
        module, _, method = format_name.partition(':')
        if '.' not in module:
            module = PUBLIC_FORMATTER_MODULE_NAME_PREFIX + module + '.' + module
        if not method:
            method = 'format_' + module.rpartition('.')[2]
        return module, method
    module_name, method_name = interpret_format_name()

    log.info('The fully qualified Python module name of the requested Seano formatter `%s` is: `%s:%s`', format_name, module_name, method_name)

    log.info('Loading the Python module `%s`...', module_name)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        log.info('%s', e)
        raise SeanoFatalError('Unable to find a Seano formatter named \'%s\' (add -v to top-level args for more information)' % (format_name,))

    log.info('Accessing the function `%s`...', method_name)
    try:
        method = getattr(module, method_name)
    except AttributeError as e:
        log.info('%s', e)
        raise SeanoFatalError('Unable to run the Seano formatter named \'%s\' (is it compatible with this version of Seano?) (add -v to top-level args for more information)' % (format_name,))

    log.info('Running the formatter...')
    method(*args)
