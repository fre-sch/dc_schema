"""Generic dataclass<->dict serde: to_dict / from_dict, alias-aware.

These use plain dataclasses only -- dc_schema stays uncoupled from MCP.
"""

import dataclasses
import enum
import typing

import pytest

import dc_schema


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


@dataclasses.dataclass
class Point:
    x: float
    y: float


@dataclasses.dataclass
class Shape:
    # an aliased field: serialises under `strokeColor`, not `stroke_color`.
    stroke_color: typing.Annotated[
        Color, dc_schema.SchemaAnnotation(alias="strokeColor")
    ]
    origin: Point
    vertices: list[Point]
    label: typing.Optional[str] = None


def test_to_dict_applies_alias_and_recurses():
    shape = Shape(
        stroke_color=Color.RED,
        origin=Point(x=0.0, y=0.0),
        vertices=[Point(x=1.0, y=2.0)],
        label="tri",
    )
    assert dc_schema.to_dict(shape) == {
        "strokeColor": "red",
        "origin": {"x": 0.0, "y": 0.0},
        "vertices": [{"x": 1.0, "y": 2.0}],
        "label": "tri",
    }


def test_to_dict_omits_none_fields():
    shape = Shape(stroke_color=Color.BLUE, origin=Point(0.0, 0.0), vertices=[])
    result = dc_schema.to_dict(shape)
    assert "label" not in result  # None -> omitted, never a literal null
    assert result == {
        "strokeColor": "blue",
        "origin": {"x": 0.0, "y": 0.0},
        "vertices": [],
    }


def test_from_dict_maps_alias_back_and_reconstructs():
    shape = dc_schema.from_dict(
        Shape,
        {
            "strokeColor": "red",
            "origin": {"x": 0.0, "y": 0.0},
            "vertices": [{"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 4.0}],
        },
    )
    assert shape.stroke_color is Color.RED  # enum reconstructed from value
    assert shape.origin == Point(0.0, 0.0)  # nested dataclass
    assert shape.vertices == [Point(1.0, 2.0), Point(3.0, 4.0)]  # list of them
    assert shape.label is None  # absent key -> field default


def test_from_dict_round_trips_to_dict():
    original = Shape(
        stroke_color=Color.BLUE,
        origin=Point(x=-1.0, y=2.5),
        vertices=[Point(x=1.0, y=1.0)],
        label="quad",
    )
    assert dc_schema.from_dict(Shape, dc_schema.to_dict(original)) == original


def test_from_dict_reconstructs_optional_single_arm_union():
    @dataclasses.dataclass
    class Node:
        child: Point | None = None

    assert dc_schema.from_dict(Node, {"child": {"x": 1.0, "y": 2.0}}) == Node(
        child=Point(1.0, 2.0)
    )
    assert dc_schema.from_dict(Node, {"child": None}) == Node(child=None)


def test_from_dict_reconstructs_dict_of_dataclasses():
    @dataclasses.dataclass
    class Atlas:
        points: dict[str, Point]

    atlas = dc_schema.from_dict(Atlas, {"points": {"a": {"x": 1.0, "y": 2.0}}})
    assert atlas.points == {"a": Point(1.0, 2.0)}


def test_to_dict_by_alias_false_uses_raw_field_names():
    shape = Shape(stroke_color=Color.RED, origin=Point(0.0, 0.0), vertices=[])
    # the aliased field falls back to its Python name; nesting is unaffected.
    assert dc_schema.to_dict(shape, by_alias=False) == {
        "stroke_color": "red",
        "origin": {"x": 0.0, "y": 0.0},
        "vertices": [],
    }


def test_from_dict_by_alias_false_matches_raw_field_names():
    shape = dc_schema.from_dict(
        Shape,
        {
            "stroke_color": "blue",
            "origin": {"x": 1.0, "y": 1.0},
            "vertices": [{"x": 2.0, "y": 2.0}],
        },
        by_alias=False,
    )
    assert shape.stroke_color is Color.BLUE
    assert shape.origin == Point(1.0, 1.0)
    assert shape.vertices == [Point(2.0, 2.0)]
    # the aliased key is ignored under by_alias=False: `stroke_color` is
    # required, so supplying only `strokeColor` leaves it unfilled.
    with pytest.raises(TypeError):
        dc_schema.from_dict(
            Shape,
            {
                "strokeColor": "red",
                "origin": {"x": 0.0, "y": 0.0},
                "vertices": [],
            },
            by_alias=False,
        )


def test_to_dict_recurses_into_dict_valued_field():
    @dataclasses.dataclass
    class Registry:
        entries: dict

    result = dc_schema.to_dict(Registry(entries={"a": Point(1.0, 2.0), "n": 3}))
    # a dict field's values recurse: the nested dataclass renders, scalars stay.
    assert result == {"entries": {"a": {"x": 1.0, "y": 2.0}, "n": 3}}


def test_to_dict_rejects_non_dataclass_and_class():
    with pytest.raises(TypeError):
        dc_schema.to_dict({"x": 1})  # a bare dict is not a dataclass instance
    with pytest.raises(TypeError):
        dc_schema.to_dict(Point)  # a dataclass *class*, not an instance


def test_by_alias_false_round_trips():
    original = Shape(
        stroke_color=Color.BLUE,
        origin=Point(x=-1.0, y=2.5),
        vertices=[Point(x=1.0, y=1.0)],
        label="quad",
    )
    raw = dc_schema.to_dict(original, by_alias=False)
    assert "stroke_color" in raw and "strokeColor" not in raw
    assert dc_schema.from_dict(Shape, raw, by_alias=False) == original
