"""PEP 604 union support (`X | Y`, `X | None`).

The generator must treat `types.UnionType` (the `|` syntax) exactly like the
equivalent `typing.Union` / `typing.Optional`.
"""

import dataclasses
import typing

from dc_schema import get_schema


@dataclasses.dataclass
class Pep604Union:
    x: int | str


@dataclasses.dataclass
class TypingUnion:
    x: typing.Union[int, str]


@dataclasses.dataclass
class Pep604Optional:
    x: str | None


@dataclasses.dataclass
class TypingOptional:
    x: typing.Optional[str]


@dataclasses.dataclass
class Pep604UnionWithNone:
    x: int | str | None


def prop(dc):
    return get_schema(dc)["properties"]["x"]


def test_pep604_union_matches_typing_union():
    assert prop(Pep604Union) == prop(TypingUnion)


def test_pep604_union_is_anyof():
    assert prop(Pep604Union) == {
        "anyOf": [{"type": "integer"}, {"type": "string"}]
    }


def test_pep604_optional_matches_typing_optional():
    assert prop(Pep604Optional) == prop(TypingOptional)


def test_pep604_optional_includes_null():
    # A single concrete type + None collapses to a `type` array
    # (see wiki nullable-union-type-array).
    assert prop(Pep604Optional) == {"type": ["string", "null"]}


def test_pep604_union_with_none():
    assert prop(Pep604UnionWithNone) == {
        "anyOf": [
            {"type": "integer"},
            {"type": "string"},
            {"type": "null"},
        ]
    }
