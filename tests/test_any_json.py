"""any-JSON support: `typing.Any` maps to `{}` (accept any value).

Bare `object` is rejected as ambiguous -- authors pick `typing.Any` (any value)
or `dict` (a JSON object).
"""

import dataclasses
import typing

import pytest

from dc_schema import get_schema


@dataclasses.dataclass
class WithAny:
    x: typing.Any


@dataclasses.dataclass
class WithAnyDefault:
    x: typing.Any = None


@dataclasses.dataclass
class WithAnyOrNone:
    x: typing.Any | None


@dataclasses.dataclass
class WithObject:
    x: object


def prop(dc):
    return get_schema(dc)["properties"]["x"]


def test_typing_any_accepts_any():
    assert prop(WithAny) == {}


def test_typing_any_keeps_default():
    # `Any` still accepts any value; a field default is threaded like any other.
    assert prop(WithAnyDefault) == {"default": None}


def test_any_or_none_arm_is_empty_schema():
    # The `Any` arm emits `{}`; the union still resolves. (`Any` already admits
    # None, so this union is redundant in practice, but must not error.)
    assert prop(WithAnyOrNone) == {"anyOf": [{}, {"type": "null"}]}


def test_bare_object_is_rejected():
    with pytest.raises(TypeError, match="ambiguous"):
        get_schema(WithObject)
