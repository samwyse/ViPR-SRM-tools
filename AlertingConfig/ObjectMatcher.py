#!/usr/bin/env python

'''\
Simplifies matching objects.

TODO:
Instead of False or True, return None or a match object, similar to re.
Add Group(key [, match=ANY]) to build a mapping of objects found during matching.
'''

# Insure maximum compatibility between Python 2.6+ and 3.x
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes, with_statement

# For when __future__ isn't enough... (Not quite willing to import six.)
import sys
PY3 = sys.version_info[0] == 3

# helper objects

class _Exec(object):
    """Generate and execure code."""
    def __init__(self, template, verbose=False):
        self.template = template
        self.verbose = verbose
    def __call__(self, *args, **kwargs):
        object = self.template.format(*args, **kwargs)
        if self.verbose:
            print(object)
        exec object in globals()

# The base from which all other objects will be derived.

class ObjectMatcher(object):
    """Base class of all object matchers."""
    def __repr__(self, _repr_running={}):
        """obj.__repr__() <==> repr(obj)"""
        return self.__class__.__name__ + '()'
    def __call__(self, other):
        """Virtual method, implemented in subclasses."""
        raise NotImplementedError()
    @staticmethod
    def compile(validator,
                 _sequence_types = (list, tuple, range) if PY3 else (list, tuple),
                 _mapping_types = (dict)
                 ):
        """Force a validator to be an ObjectMatcher.
This is a bit of a cheat, since it has various subclasses hard-coded into it."""
        if isinstance(validator, ObjectMatcher):
            return validator
        if isinstance(validator, _sequence_types):
            return SequenceMatcher(validator)
        if isinstance(validator, _mapping_types):
            return MappingMatcher(validator)
        return Eq(validator)

class Exists(ObjectMatcher):
    """Confirm that an object exists.
This is mostly useful with MappingMatcher, to confirm a key is present.

>>> IsExtant = Exists()

>>> IsExtant
Exists()

>>> all(IsExtant(item) for item in (None, 0, '', 0.0))
True
"""
    def __call__(self, other):
        return True

class Missing(ObjectMatcher):
    """Confirm that an object does not exist.
This is mostly useful with MappingMatcher, to confirm a key is missing.

>>> IsAbsent = Missing()

>>> IsAbsent
Missing()

>>> IsAbsent(0)
False
"""
    def __call__(self, other):
        return False

class IsNone(ObjectMatcher):
    """Confirm that an object is None.

>>> NONE = IsNone()

>>> NONE
IsNone()

>>> NONE(None)
True

>>> any(NONE(item) for item in (0, '', 0.0))
False
"""
    def __call__(self, other):
        return other is None

class Truth(ObjectMatcher):
    """Confirm that an object represents a true value.

>>> TRUE = Truth()

>>> TRUE
Truth()

>>> any(TRUE(item) for item in (None, 0, '', 0.0))
False

>>> all(TRUE(item) for item in (True, 1, 'x', 1.0))
True
"""
    def __call__(self, other):
        return bool(other)

class BinaryMatcher(ObjectMatcher):
    """Base of all matchers taking a single argument.
"""
    def __init__(self, validate):
        self.validate = validate
    def __repr__(self, _repr_running={}):
        """obj.__repr__() <==> repr(obj)"""
        return '%s(%r)' % (self.__class__.__name__, self.validate)

class Passes(BinaryMatcher):
    """Confirms validation via an arbitrary predicate.
(All other binary matchers could be considered optimizations of this one.)
"""
    def __call__(self, other):
        return self.validate(other)

class In(BinaryMatcher):
    """comfirms presence in a container.

>>> SmallPrime = In(set([2, 3, 5, 7, 11, 13, 17, 19, 23]))

>>> SmallPrime
In(set([2, 3, 5, 7, 11, 13, 17, 19, 23]))

In({2, 3, 5, 7, 11, 13, 17, 19, 23})

>>> SmallPrime(0)
False

>>> SmallPrime(11)
True

>>> IsVowel = In('aeiou')

>>> IsVowel
In(u'aeiou')

In('aeiou')

>>> IsVowel('a')
True

>>> IsVowel('z')
False
"""
    def __call__(self, other):
        return other in self.validate

# Template to generate relational operators
_binary_template = _Exec('''\
class {name}(BinaryMatcher):
    """
>>> {name}Zero = {name}(0)

>>> {name}Zero
{name}(0)

>>> {name}Zero(-1)
{less}

>>> {name}Zero(0)
{same}

>>> {name}Zero(+1)
{more}
"""
    def __call__(self, other):
        return other {oper} self.validate
''')

# The relational operators
_comparisons = [
    {'less': -1 == 0, 'more': +1 == 0, 'name': 'Eq', 'oper': '==', 'same': 0 == 0},
    {'less': -1 != 0, 'more': +1 != 0, 'name': 'Ne', 'oper': '!=', 'same': 0 != 0},
    {'less': -1 < 0, 'more': +1 < 0, 'name': 'Lt', 'oper': '<', 'same': 0 < 0},
    {'less': -1 > 0, 'more': +1 > 0, 'name': 'Gt', 'oper': '>', 'same': 0 > 0},
    {'less': -1 <= 0, 'more': +1 <= 0, 'name': 'Le', 'oper': '<=', 'same': 0 <= 0},
    {'less': -1 >= 0, 'more': +1 >= 0, 'name': 'Ge', 'oper': '>=', 'same': 0 >= 0}]

# Generate the classes
for _oper in _comparisons:
    _binary_template(**_oper)

# Template to generate built-in predicates
_class_template = '''\
class {name}(BinaryMatcher):
    """
"""
    def __call__(self, other):
        return {predicate}(other, self.validate)
'''

# The actual comparisons
_predicates = [
    {'name': _p, 'predicate': _p.lower()}
    for _p in ('All', 'Any', 'Callable', 'IsInstance', 'IsSubclass')
    ]

class SequenceMatcher(BinaryMatcher):
    """Confirm a possibly-nested container matches a pattern.

>>> ANY = Exists()

>>> t = SequenceMatcher((ANY, 'bar', (ANY, ANY)))

>>> t
SequenceMatcher((Exists(), Eq(u'bar'), SequenceMatcher((Exists(), Exists()))))

>>> t(('foo', 'bar', (42, 'spam')))
True

>>> t(('foo', 'baz', (42, 'spam')))
False

"""
    def __init__(self, validate):
        self.validate = tuple( self.compile(v) for v in validate )
    def __call__(self, other):
        if len(self.validate) != len(other):
            return False
        for a, b in zip(self.validate, other):
            if not a(b):
                return False
        return True

class MappingMatcher(BinaryMatcher):
    """
Confirm a mapping has the indicated keys.

By leveraging the Exists class, we can confirm the presentce of a key
without caring about its validate.

>>> d = MappingMatcher({'foo': Exists(), 'bar': Missing()})

>>> d
MappingMatcher({u'foo': Exists(), u'bar': Missing()})

MappingMatcher({'foo': Exists(), 'bar': Missing()})

Shouldn't match non-mapping objects

>>> d(0)
False

>>> d({'foo': 0})
True

>>> d({'foo': 0, 'bar': 0})
False

>>> d({'foo': 0, 'baz': 0})
True

For the user's convenience, keyword arguments can be used, and
values that aren't ObjectMatchers will be converted to Eq(value).

>>> d = MappingMatcher(foo=0)

>>> d
MappingMatcher({'foo': Eq(0)})

>>> d({'foo': 0})
True

>>> d({'foo': 1})
False
"""
    def __init__(self, *args, **kwds):
        if len(args) > 1:
            raise TypeError('expected at most 1 argument, got %d' % len(args))
        try:
            args = args[0].items()
        except (IndexError, AttributeError):
            pass
        from itertools import chain
        self.validate = dict((key, self.compile(value))
                             for key, value in chain(args, kwds.items()))
    def __call__(self, other):
        for key, validate in self.validate.items():
            try:
                if not validate(other[key]):
                    return False
            except KeyError:
                return type(validate) == Missing
            except TypeError:
                return False
        return True

__all__ = []
_g = globals().copy()
for _name in _g:
    try:
        if issubclass(_g[_name], ObjectMatcher):
            __all__.append(_name)
    except TypeError:
        pass
    
if __name__ == "__main__":
    import doctest
    doctest.testmod()
