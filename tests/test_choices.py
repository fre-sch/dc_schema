"""`Choices`: an inline set of string choices, titled or untitled.

A mapping is titled and emits `{const, title}` branches; a sequence is untitled
and emits a plain `enum`. Cardinality comes from the container -- `str` picks
one (`oneOf`), `list[str]` picks several (`items.anyOf`).
"""

import dataclasses
import typing as t

import jsonschema
import pytest

from dc_schema import Choices, SchemaAnnotation, get_schema

DOUGHS = {"thin": "Thin & Crispy", "deep-dish": "Chicago Deep Dish"}
TOPPINGS = {"pepperoni": "Pepperoni", "olive": "Black Olives"}


@dataclasses.dataclass
class TitledScalar:
    x: t.Annotated[str, Choices(DOUGHS)]


@dataclasses.dataclass
class TitledCollection:
    x: t.Annotated[list[str], Choices(TOPPINGS)]


@dataclasses.dataclass
class UntitledScalar:
    x: t.Annotated[str, Choices(list(DOUGHS))]


@dataclasses.dataclass
class UntitledCollection:
    x: t.Annotated[list[str], Choices(list(TOPPINGS))]


def prop(dc):
    return get_schema(dc)["properties"]["x"]


def test_titled_scalar_emits_one_of():
    assert prop(TitledScalar) == {
        "type": "string",
        "oneOf": [
            {"const": "thin", "title": "Thin & Crispy"},
            {"const": "deep-dish", "title": "Chicago Deep Dish"},
        ],
    }


def test_titled_collection_emits_items_any_of():
    assert prop(TitledCollection) == {
        "type": "array",
        "items": {
            "anyOf": [
                {"const": "pepperoni", "title": "Pepperoni"},
                {"const": "olive", "title": "Black Olives"},
            ]
        },
    }


def test_untitled_scalar_emits_enum():
    assert prop(UntitledScalar) == {
        "type": "string",
        "enum": ["thin", "deep-dish"],
    }


def test_untitled_collection_emits_items_enum():
    assert prop(UntitledCollection) == {
        "type": "array",
        "items": {"enum": ["pepperoni", "olive"]},
    }


# --- keywords ride along, the payload does not ------------------------------


@dataclasses.dataclass
class WithKeywords:
    x: t.Annotated[
        list[str],
        Choices(
            TOPPINGS,
            title="Toppings",
            description="Pick any.",
            min_items=1,
            max_items=3,
            alias="pizza-toppings",
        ),
    ]


def test_keywords_emit_beside_the_choice_body():
    assert get_schema(WithKeywords)["properties"]["pizza-toppings"] == {
        "type": "array",
        "items": {
            "anyOf": [
                {"const": "pepperoni", "title": "Pepperoni"},
                {"const": "olive", "title": "Black Olives"},
            ]
        },
        "title": "Toppings",
        "description": "Pick any.",
        "minItems": 1,
        "maxItems": 3,
    }


def test_alias_renames_the_property():
    schema = get_schema(WithKeywords)
    assert list(schema["properties"]) == ["pizza-toppings"]
    assert schema["required"] == ["pizza-toppings"]


def test_choices_payload_never_leaks():
    assert "choices" not in Choices(DOUGHS).schema()


# --- a field default rides along, as it does for every other type -----------


@dataclasses.dataclass
class WithDefault:
    x: t.Annotated[str, Choices(DOUGHS)] = "thin"


def test_field_default_emits_beside_the_choice_body():
    assert prop(WithDefault)["default"] == "thin"


# --- construction-time rules ------------------------------------------------


def test_empty_choices_raise():
    with pytest.raises(ValueError, match="at least one choice"):
        Choices([])
    with pytest.raises(ValueError, match="at least one choice"):
        Choices({})


def test_duplicate_value_raises_naming_it():
    with pytest.raises(ValueError, match="duplicate choice value: 'thin'"):
        Choices(["thin", "deep-dish", "thin"])


def test_non_string_value_raises_naming_it():
    with pytest.raises(TypeError, match="must be a string: 1"):
        Choices(["thin", 1])


def test_non_string_title_raises_naming_its_value():
    with pytest.raises(TypeError, match="title of choice 'thin' must be"):
        Choices({"thin": 1})


def test_a_bare_string_is_not_a_choice_set():
    with pytest.raises(TypeError, match="received the string 'thin'"):
        Choices("thin")


def test_payload_is_positional_keywords_are_not():
    annotation = Choices(DOUGHS, description="How the base is made.")
    assert annotation.choices == DOUGHS
    assert annotation.description == "How the base is made."


def test_schema_annotation_is_keyword_only():
    with pytest.raises(TypeError):
        SchemaAnnotation("some-alias")


# --- unsupported containers -------------------------------------------------


@dataclasses.dataclass
class ChoicesOnInt:
    x: t.Annotated[int, Choices(["thin"])]


@dataclasses.dataclass
class ChoicesOnSet:
    x: t.Annotated[set[str], Choices(["thin"])]


@pytest.mark.parametrize("dc", [ChoicesOnInt, ChoicesOnSet])
def test_choices_rejects_other_containers(dc):
    with pytest.raises(TypeError, match="Choices annotates"):
        get_schema(dc)


# --- the emissions are valid, and validate --------------------------------


@pytest.mark.parametrize(
    "dc",
    [TitledScalar, TitledCollection, UntitledScalar, UntitledCollection],
)
def test_generated_schemas_are_valid_schemas(dc):
    jsonschema.Draft202012Validator.check_schema(get_schema(dc))


@pytest.mark.parametrize(
    "dc,valid,unknown,titled",
    [
        (TitledScalar, "thin", "stuffed", "Thin & Crispy"),
        (UntitledScalar, "thin", "stuffed", "Thin & Crispy"),
        (TitledCollection, ["olive"], ["anchovy"], ["Black Olives"]),
        (UntitledCollection, ["olive"], ["anchovy"], ["Black Olives"]),
    ],
)
def test_only_choice_values_validate(dc, valid, unknown, titled):
    validator = jsonschema.Draft202012Validator(get_schema(dc))
    validator.validate({"x": valid})
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"x": unknown})
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"x": titled})
