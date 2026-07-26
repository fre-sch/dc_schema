"""`SchemaAnnotation.additional_properties` closes/shapes object bodies."""

import dataclasses
import typing

from jsonschema.validators import Draft202012Validator

from dc_schema import SchemaAnnotation, get_schema


def test_false_closes_the_object():
    @dataclasses.dataclass
    class Closed:
        a: int

        class SchemaConfig:
            annotation = SchemaAnnotation(additional_properties=False)

    schema = get_schema(Closed)
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    # extras are rejected against the generated schema.
    validator = Draft202012Validator(schema)
    assert validator.is_valid({"a": 1})
    assert not validator.is_valid({"a": 1, "b": 2})


def test_true_allows_any_extra():
    @dataclasses.dataclass
    class Open:
        a: int

        class SchemaConfig:
            annotation = SchemaAnnotation(additional_properties=True)

    schema = get_schema(Open)
    assert schema["additionalProperties"] is True


def test_type_generates_a_subschema():
    @dataclasses.dataclass
    class StringExtras:
        a: int

        class SchemaConfig:
            annotation = SchemaAnnotation(additional_properties=str)

    schema = get_schema(StringExtras)
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] == {"type": "string"}
    validator = Draft202012Validator(schema)
    assert validator.is_valid({"a": 1, "note": "ok"})
    assert not validator.is_valid({"a": 1, "note": 2})


def test_unset_omits_the_keyword():
    @dataclasses.dataclass
    class Plain:
        a: int

    assert "additionalProperties" not in get_schema(Plain)


def test_closes_a_referenced_def_not_just_the_root():
    @dataclasses.dataclass
    class Child:
        a: int

        class SchemaConfig:
            annotation = SchemaAnnotation(additional_properties=False)

    @dataclasses.dataclass
    class Parent:
        child: Child

    schema = get_schema(Parent)
    Draft202012Validator.check_schema(schema)
    child = schema["$defs"]["Child"]
    assert child["additionalProperties"] is False
    # the closure lives in the def body, not beside the field's `$ref`.
    assert "additionalProperties" not in schema["properties"]["child"]


def test_additional_properties_is_not_a_field_site_keyword():
    # As a field annotation it is a directive, not a schema keyword: it must not
    # leak into the field's schema body.
    @dataclasses.dataclass
    class Holder:
        value: typing.Annotated[
            int, SchemaAnnotation(additional_properties=False)
        ]

    assert get_schema(Holder)["properties"]["value"] == {"type": "integer"}
