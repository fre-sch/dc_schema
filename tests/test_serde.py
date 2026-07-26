"""Generic dataclass<->dict serde: to_dict / from_dict, alias-aware.

These use plain dataclasses only -- dc_schema stays uncoupled from MCP.
"""

import dataclasses
import enum
import typing

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
        Color, dc_schema.SchemaAnnotation(name="strokeColor")
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
