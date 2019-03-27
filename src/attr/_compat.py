from __future__ import absolute_import, division, print_function

import platform
import sys
import types
import warnings


PY2 = sys.version_info[0] == 2
PYPY = platform.python_implementation() == "PyPy"


if PYPY or sys.version_info[:2] >= (3, 6):
    ordered_dict = dict
else:
    from collections import OrderedDict

    ordered_dict = OrderedDict


if PY2:
    from UserDict import IterableUserDict
    from collections import Mapping, Sequence  # noqa

    # We 'bundle' isclass instead of using inspect as importing inspect is
    # fairly expensive (order of 10-15 ms for a modern machine in 2016)
    def isclass(klass):
        return isinstance(klass, (type, types.ClassType))

    # TYPE is used in exceptions, repr(int) is different on Python 2 and 3.
    TYPE = "type"

    def iteritems(d):
        return d.iteritems()

    # Python 2 is bereft of a read-only dict proxy, so we make one!
    class ReadOnlyDict(IterableUserDict):
        """
        Best-effort read-only dict wrapper.
        """

        def __setitem__(self, key, val):
            # We gently pretend we're a Python 3 mappingproxy.
            raise TypeError(
                "'mappingproxy' object does not support item assignment"
            )

        def update(self, _):
            # We gently pretend we're a Python 3 mappingproxy.
            raise AttributeError(
                "'mappingproxy' object has no attribute 'update'"
            )

        def __delitem__(self, _):
            # We gently pretend we're a Python 3 mappingproxy.
            raise TypeError(
                "'mappingproxy' object does not support item deletion"
            )

        def clear(self):
            # We gently pretend we're a Python 3 mappingproxy.
            raise AttributeError(
                "'mappingproxy' object has no attribute 'clear'"
            )

        def pop(self, key, default=None):
            # We gently pretend we're a Python 3 mappingproxy.
            raise AttributeError(
                "'mappingproxy' object has no attribute 'pop'"
            )

        def popitem(self):
            # We gently pretend we're a Python 3 mappingproxy.
            raise AttributeError(
                "'mappingproxy' object has no attribute 'popitem'"
            )

        def setdefault(self, key, default=None):
            # We gently pretend we're a Python 3 mappingproxy.
            raise AttributeError(
                "'mappingproxy' object has no attribute 'setdefault'"
            )

        def __repr__(self):
            # Override to be identical to the Python 3 version.
            return "mappingproxy(" + repr(self.data) + ")"

    def metadata_proxy(d):
        res = ReadOnlyDict()
        res.data.update(d)  # We blocked update, so we have to do it like this.
        return res

    def just_warn(*args, **kw):  # pragma: nocover
        """
        We only warn on Python 3 because we are not aware of any concrete
        consequences of not setting the cell on Python 2.
        """


else:  # Python 3 and later.
    from collections.abc import Mapping, Sequence  # noqa

    def just_warn(*args, **kw):
        """
        We only warn on Python 3 because we are not aware of any concrete
        consequences of not setting the cell on Python 2.
        """
        warnings.warn(
            "Running interpreter doesn't sufficiently support code object "
            "introspection.  Some features like bare super() or accessing "
            "__class__ will not work with slotted classes.",
            RuntimeWarning,
            stacklevel=2,
        )

    def isclass(klass):
        return isinstance(klass, type)

    TYPE = "class"

    def iteritems(d):
        return d.items()

    def metadata_proxy(d):
        return types.MappingProxyType(dict(d))


def make_set_closure_cell():
    """Return a function of two arguments (cell, value) which sets
    the value stored in the closure cell `cell` to `value`.
    """
    # pypy makes this easy. (It also supports the logic below, but
    # why not do the easy/fast thing?)
    if PYPY:  # pragma: no cover

        def set_closure_cell(cell, value):
            cell.__setstate__((value,))

        return set_closure_cell

    # Otherwise gotta do it the hard way.

    # Create a function that will set its first cellvar to `value`.
    def set_first_cellvar_to(value):
        x = value
        return

        # This function will be eliminated as dead code, but
        # not before its reference to `x` forces `x` to be
        # represented as a closure cell rather than a local.
        def force_x_to_be_a_cell():
            return x

    try:
        # Extract the code object and make sure our assumptions about
        # the closure behavior are correct.
        if PY2:
            co = set_first_cellvar_to.func_code
        else:
            co = set_first_cellvar_to.__code__
        if co.co_cellvars != ("x",) or co.co_freevars != ():
            raise AssertionError

        # Convert this code object to a code object that sets the
        # function's first _freevar_ (not cellvar) to the argument.
        args = [co.co_argcount]
        if not PY2:
            args.append(co.co_kwonlyargcount)
        args.extend(
            [
                co.co_nlocals,
                co.co_stacksize,
                co.co_flags,
                co.co_code,
                co.co_consts,
                co.co_names,
                co.co_varnames,
                co.co_filename,
                co.co_name,
                co.co_firstlineno,
                co.co_lnotab,
                # These two arguments are reversed:
                co.co_cellvars,
                co.co_freevars,
            ]
        )
        set_first_freevar_code = types.CodeType(*args)

        def set_closure_cell(cell, value):
            # Create a function using the set_first_freevar_code,
            # whose first closure cell is `cell`. Calling it will
            # change the value of that cell.
            setter = types.FunctionType(
                set_first_freevar_code, {}, "setter", (), (cell,)
            )
            # And call it to set the cell.
            setter(value)

        # Make sure it works on this interpreter:
        def make_func_with_cell():
            x = None

            def func():
                return x

            return func

        if PY2:
            cell = make_func_with_cell().func_closure[0]
        else:
            cell = make_func_with_cell().__closure__[0]
        set_closure_cell(cell, 100)
        if cell.cell_contents != 100:
            raise AssertionError

    except Exception:
        return just_warn
    else:
        return set_closure_cell


set_closure_cell = make_set_closure_cell()
