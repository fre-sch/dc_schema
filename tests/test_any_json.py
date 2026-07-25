"""any-JSON support: `object` / `typing.Any` map to `{}` (accept any value)."""

import dataclasses
import typing

from dc_schema import get_schema


@dataclasses.dataclass
class WithObject:
    x: object


@dataclasses.dataclass
class WithAny:
    x: typing.Any


@dataclasses.dataclass
class WithObjectOrNone:
    x: object | None


def prop(dc):
    return get_schema(dc)["properties"]["x"]


def test_object_accepts_any():
    assert prop(WithObject) == {}


def test_typing_any_accepts_any():
    assert prop(WithAny) == {}


def test_object_or_none_is_anyof():
    # object -> {} (any), None -> null; requires PEP 604 union support too.
    assert prop(WithObjectOrNone) == {"anyOf": [{}, {"type": "null"}]}
