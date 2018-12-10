"""
Assemblyline's built in Object Document Model tool.

The classes in this module can be composed to build database
independent data models in python. This gives us:
- single source of truth for our data schemas
- database independent serialization
- type checking


"""

import re
import json
import copy
import arrow
import typing

from datetime import datetime
from dateutil.tz import tzutc

from assemblyline.common import forge

DATEFORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
UTC_TZ = tzutc()
FIELD_SANITIZER = re.compile("^[a-z][a-z0-9_]*$")
BANNED_FIELDS = {"id"}


def flat_to_nested(data: dict):
    sub_data = {}
    nested_keys = []
    for key, value in data.items():
        if '.' in key:
            child, sub_key = key.split('.', 1)
            nested_keys.append(child)
            try:
                sub_data[child][sub_key] = value
            except KeyError:
                sub_data[child] = {sub_key: value}
        else:
            sub_data[key] = value

    for key in nested_keys:
        sub_data[key] = flat_to_nested(sub_data[key])

    return sub_data


class KeyMaskException(KeyError):
    pass


class UndefinedFunction(Exception):
    pass


class _Field:
    def __init__(self, name=None, index=None, store=None, copyto=None, default=None, default_set=None):
        self.index = index
        self.store = store
        self.copyto = []
        if isinstance(copyto, str):
            self.copyto.append(copyto)
        elif copyto:
            self.copyto.extend(copyto)

        self.name = name
        self.getter_function = None
        self.setter_function = None

        self.default = default
        self.default_set = True if default is not None else default_set

    # noinspection PyProtectedMember
    def __get__(self, obj, objtype=None):
        """Read the value of this field from the model instance (obj)."""
        if obj is None:
            return obj
        if self.name in obj._odm_removed:
            raise KeyMaskException(self.name)
        if self.getter_function:
            return self.getter_function(obj, obj._odm_py_obj[self.name])
        return obj._odm_py_obj[self.name]

    # noinspection PyProtectedMember
    def __set__(self, obj, value):
        """Set the value of this field, calling a setter method if available."""
        if self.name in obj._odm_removed:
            raise KeyMaskException(self.name)
        value = self.check(value)
        if self.setter_function:
            value = self.setter_function(obj, value)
        obj._odm_py_obj[self.name] = value

    def getter(self, method):
        """Decorator to create getter method for a field."""
        out = copy.deepcopy(self)
        out.getter_function = method
        return out

    def setter(self, method):
        """
        Let fields be used as a decorator to define a setter method.

        >>> expiry = Date()
        >>>
        >>> # noinspection PyUnusedLocal
        >>> @expiry.setter
        >>> def expiry(self, assign, value):
        >>>     assert value
        >>>     assign(value)
        """
        out = copy.deepcopy(self)
        out.setter_function = method
        return out

    def apply_defaults(self, index, store):
        """Used by the model decorator to pass through default parameters."""
        if self.index is None:
            self.index = index
        if self.store is None:
            self.store = store

    def fields(self):
        """
        Return the subfields/modified field data.

        For simple fields this is an identity function.
        """
        return {'': self}

    def check(self, value, **kwargs):
        raise UndefinedFunction("This function is not defined in the default field. "
                                "Each fields has to have their own definition")


class _DeletedField:
    pass


class Date(_Field):
    """A field storing a datetime value."""

    def check(self, value, **kwargs):
        # Use the arrow library to transform ??? to a datetime
        try:
            return datetime.strptime(value, DATEFORMAT).replace(tzinfo=UTC_TZ)
        except (TypeError, ValueError):
            return arrow.get(value).datetime


class Boolean(_Field):
    """A field storing a boolean value."""

    def check(self, value, **kwargs):
        return bool(value)


class Keyword(_Field):
    """
    A field storing a short string with a technical interpritation.

    Examples: file hashes, service names, document ids
    """

    def check(self, value, **kwargs):
        if not value:
            if self.default_set:
                value = self.default
            else:
                raise ValueError("Empty strings are not allow without defaults")
        return str(value)


class Enum(Keyword):
    def __init__(self, values, *args, **kwargs):
        """
        An expanded classification is one that controls the access to the document
        which holds it. If a classification field is only meant to store classification
        information and not enforce it, expand should be false.
        """
        super().__init__(*args, **kwargs)
        self.values = set(values)

    def check(self, value, **kwargs):
        if not value:
            if self.default_set:
                value = self.default
            else:
                raise ValueError("Empty enums are not allow without defaults")
        if value not in self.values:
            raise ValueError(f"{value} not in the possible values: {self.values}")
        return str(value)


class Text(_Field):
    """A field storing human readable text data."""

    def check(self, value, **kwargs):
        if not value:
            if self.default_set:
                value = self.default
            else:
                raise ValueError("Empty strings are not allow without defaults")

        return str(value)


class IndexText(_Field):
    """A special field with special processing rules to simplify searching."""

    def check(self, value, **kwargs):
        return str(value)


class Integer(_Field):
    """A field storing an integer value."""

    def check(self, value, **kwargs):
        return int(value)


class Float(_Field):
    """A field storing a floating point value."""

    def check(self, value, **kwargs):
        return float(value)


class ClassificationObject(object):
    def __init__(self, engine, value, is_uc=False):
        self.engine = engine
        self.is_uc = is_uc
        self.value = engine.normalize_classification(value, skip_auto_select=is_uc)

    def min(self, other):
        return ClassificationObject(self.engine,
                                    self.engine.min_classification(self.value, other.value),
                                    is_uc=self.is_uc)

    def max(self, other):
        return ClassificationObject(self.engine,
                                    self.engine.max_classification(self.value, other.value),
                                    is_uc=self.is_uc)

    def intersect(self, other):
        return ClassificationObject(self.engine,
                                    self.engine.intersect_user_classification(self.value, other.value),
                                    is_uc=self.is_uc)

    def small(self):
        return self.engine.normalize_classification(self.value, long_format=False, skip_auto_select=self.is_uc)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return self.value != other.value

    def __le__(self, other):
        return self.engine.is_accessible(other.value, self.value)

    def __lt__(self, other):
        return self.engine.is_accessible(other.value, self.value)

    def __ge__(self, other):
        return self.engine.is_accessible(self.value, other.value)

    def __gt__(self, other):
        return not self.engine.is_accessible(other.value, self.value)


class Classification(Keyword):
    """A field storing access control classification."""
    def __init__(self, *args, is_user_classification=False,
                 yml_config="/etc/assemblyline/classification.yml", **kwargs):
        """
        An expanded classification is one that controls the access to the document
        which holds it.
        """
        super().__init__(*args, **kwargs)
        self.engine = forge.get_classification(yml_config=yml_config)
        self.is_uc = is_user_classification

    def check(self, value, **kwargs):
        if isinstance(value, ClassificationObject):
            return ClassificationObject(self.engine, value.value, is_uc=self.is_uc)
        return ClassificationObject(self.engine, value, is_uc=self.is_uc)


class TypedList(list):

    def __init__(self, type_p, *items):
        super().__init__([type_p.check(el) for el in items])
        self.type = type_p

    def append(self, item):
        super().append(self.type.check(item))

    def extend(self, sequence):
        super().extend(self.type.check(item) for item in sequence)

    def insert(self, index, item):
        super().insert(index, self.type.check(item))

    def __setitem__(self, index, item):
        if isinstance(index, slice):
            item = [self.type.check(val) for val in item]
            super().__setitem__(index, item)
        else:
            super().__setitem__(index, self.type.check(item))


class List(_Field):
    """A field storing a sequence of typed elements."""

    def __init__(self, child_type, **kwargs):
        super().__init__(**kwargs)
        self.child_type = child_type

    def check(self, value, **kwargs):
        if isinstance(self.child_type, Compound) and isinstance(value, dict):
            # Search queries of list of compound fields will return dotted paths of list of
            # values. When processed through the flat_fields function, since this function
            # has no idea about the data layout, it will transform the dotted paths into
            # a dictionary of items then contains a list of object instead of a list
            # of dictionaries with single items.

            # The following piece of code transforms the dictionary of list into a list of
            # dictionaries so the rest of the model validation can go through.
            return TypedList(self.child_type, *[dict(zip(value, t)) for t in zip(*value.values())])

        return TypedList(self.child_type, *value)

    def apply_defaults(self, index, store):
        """Initialize the default settings for the child field."""
        # First apply the default to the list itself
        super().apply_defaults(index, store)
        # Then pass through the initialized values on the list to the child type
        self.child_type.apply_defaults(self.index, self.store)

    def fields(self):
        out = dict()
        for name, field_data in self.child_type.fields().items():
            field_data = copy.deepcopy(field_data)
            field_data.apply_defaults(self.index, self.store)
            out[name] = field_data
        return out


class TypedMapping(dict):
    def __init__(self, type_p, **items):
        for key in items.keys():
            if not FIELD_SANITIZER.match(key):
                raise KeyError(f"Illegal key: {key}")
        super().__init__({key: type_p.check(el) for key, el in items.items()})
        self.type = type_p

    def __setitem__(self, key, item):
        if not FIELD_SANITIZER.match(key):
            raise KeyError(f"Illegal key: {key}")
        return super().__setitem__(key, self.type.check(item))

    def update(self, **data):
        for key in data.keys():
            if not FIELD_SANITIZER.match(key):
                raise KeyError(f"Illegal key: {key}")
        return super().update({key: self.type.check(item) for key, item in data.items()})


class Mapping(_Field):
    """A field storing a sequence of typed elements."""

    def __init__(self, child_type, **kwargs):
        super().__init__(**kwargs)
        self.child_type = child_type

    def check(self, value, **kwargs):
        return TypedMapping(self.child_type, **value)

    def apply_defaults(self, index, store):
        """Initialize the default settings for the child field."""
        # First apply the default to the list itself
        super().apply_defaults(index, store)
        # Then pass through the initialized values on the list to the child type
        self.child_type.apply_defaults(self.index, self.store)


class Compound(_Field):
    def __init__(self, field_type, **kwargs):
        super().__init__(**kwargs)
        self.child_type = field_type

    def check(self, value, mask=None):
        return self.child_type(value, mask=mask)

    def fields(self):
        out = dict()
        for name, field_data in self.child_type.fields().items():
            field_data = copy.deepcopy(field_data)
            field_data.apply_defaults(self.index, self.store)
            out[name] = field_data
        return out


class Model:
    @classmethod
    def name(cls):
        return cls.__name__

    @classmethod
    def fields(cls, skip_mappings=False) -> typing.Mapping[str, _Field]:
        """
        Describe the elements of the model.

        For compound fields return the field object.

        Args:
            skip_mappings (bool): Skip over mappings where the real subfield names are unknown.
        """
        if skip_mappings and hasattr(cls, '_odm_field_cache_skip'):
            return cls._odm_field_cache_skip

        if not skip_mappings and hasattr(cls, '_odm_field_cache'):
            return cls._odm_field_cache

        out = dict()
        for name, field_data in cls.__dict__.items():
            if isinstance(field_data, _Field):
                if skip_mappings and isinstance(field_data, Mapping):
                    continue
                out[name] = field_data

        if skip_mappings:
            cls._odm_field_cache_skip = out
        else:
            cls._odm_field_cache = out
        return out

    @classmethod
    def flat_fields(cls, skip_mappings=False) -> typing.Mapping[str, _Field]:
        """
        Describe the elements of the model.

        Recurse into compound fields, concatenating the names with '.' separators.

        Args:
            skip_mappings (bool): Skip over mappings where the real subfield names are unknown.
        """
        out = dict()
        for name, field_data in cls.__dict__.items():
            if isinstance(field_data, _Field):
                if skip_mappings and isinstance(field_data, Mapping):
                    continue
                for sub_name, sub_data in field_data.fields().items():
                    if skip_mappings and isinstance(sub_data, Mapping):
                        continue
                    out[(name + '.' + sub_name).strip('.')] = sub_data
        return out

    def __init__(self, data: dict = None, mask: list = tuple(), docid=None):
        if data is None:
            data = {}
        if not hasattr(data, 'items'):
            raise TypeError('Model must be constructed with dict like')
        self._odm_py_obj = {}
        self.id = docid

        # Parse the field mask for sub models
        mask_map = {}
        if mask:
            for entry in mask:
                if '.' in entry:
                    child, sub_key = entry.split('.', 1)
                    try:
                        mask_map[child].append(sub_key)
                    except KeyError:
                        mask_map[child] = [sub_key]
                else:
                    mask_map[entry] = None

        # Get the list of fields we expect this object to have
        fields = self.fields()
        self._odm_removed = {}
        if mask:
            self._odm_removed = {k: v for k, v in fields.items() if k not in mask_map}
            fields = {k: v for k, v in fields.items() if k in mask_map}

        # Trim out keys that actually belong to sub sections
        sub_data = {}
        for key, value in list(data.items()):
            if '.' in key:
                del data[key]
                child, sub_key = key.split('.', 1)
                try:
                    sub_data[child][sub_key] = value
                except KeyError:
                    sub_data[child] = {sub_key: value}
        data.update(sub_data)

        # Check to make sure we can use all the data we are given
        unused_keys = set(data.keys()) - set(fields.keys())
        if unused_keys:
            raise ValueError("{} created with unexpected parameters: {}".format(self.__class__.__name__, unused_keys))

        # Pass each value through it's respective validator, and store it
        for name, field_type in fields.items():
            params = {}
            if name in mask_map and mask_map[name]:
                params['mask'] = mask_map[name]

            try:
                value = data[name]
            except KeyError:
                if field_type.default_set:
                    value = copy.copy(field_type.default)
                else:
                    raise ValueError('{} expected a parameter named {}'.format(self.__class__.__name__, name))

            self._odm_py_obj[name] = field_type.check(value, **params)

    def as_primitives(self):
        """Convert the object back into primatives that can be json serialized."""
        out = {}

        fields = self.fields()
        for key, value in self._odm_py_obj.items():
            field_type = fields[key]
            if value is not None or (value is None and field_type.default_set):
                if isinstance(value, Model):
                    out[key] = value.as_primitives()
                elif isinstance(value, datetime):
                    out[key] = value.strftime(DATEFORMAT)
                elif isinstance(value, TypedMapping):
                    out[key] = {k: v.as_primitives() if isinstance(v, Model) else v for k, v in value.items()}
                elif isinstance(value, (List, TypedList)):
                    out[key] = [v.as_primitives() if isinstance(v, Model) else v for v in value]
                elif isinstance(value, ClassificationObject):
                    out[key] = str(value)
                else:
                    out[key] = value
        return out

    def json(self):
        return json.dumps(self.as_primitives())

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        if len(self._odm_py_obj) != len(other._odm_py_obj):
            return False

        for name, field in self.fields().items():
            if name in self._odm_removed:
                continue
            if field.__get__(self) != field.__get__(other):
                return False

        return True

    def __repr__(self):
        if self.id:
            return f"<{self.__class__.__name__} [{self.id}] {self.json()}>"
        return f"<{self.__class__.__name__} {self.json()}>"


def model(index=None, store=None):
    """Decorator to create model objects."""
    def _finish_model(cls):
        for name, field_data in cls.fields().items():
            if not FIELD_SANITIZER.match(name) or name in BANNED_FIELDS:
                raise ValueError(f"Illegal variable name: {name}")
            field_data.name = name
            field_data.apply_defaults(index=index, store=store)
        return cls
    return _finish_model
