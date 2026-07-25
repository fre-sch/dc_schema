"""Field property-name alias via `SchemaAnnotation(name=...)`.

A field keeps its (snake_case) Python name but takes the alias as its property
name in `properties`/`required`. The alias is a directive, never a keyword in
the field's schema body. See wiki decision mcp-type-modeling.
"""

import dataclasses
import typing

from dc_schema import get_schema, SchemaAnnotation


@dataclasses.dataclass
class DcAlias:
    website_url: typing.Annotated[
        str, SchemaAnnotation(name="websiteUrl", format="uri")
    ]
    list_changed: typing.Annotated[
        bool | None, SchemaAnnotation(name="listChanged")
    ] = None
    plain: int = 0


def test_alias_renames_property_and_required():
    schema = get_schema(DcAlias)
    assert schema["properties"] == {
        # aliased to the wire name; `name` never leaks into the body, `format`
        # (a real keyword) does.
        "websiteUrl": {"type": "string", "format": "uri"},
        # alias-only annotation on `X | None` still collapses to a type array.
        "listChanged": {"type": ["boolean", "null"], "default": None},
        "plain": {"type": "integer", "default": 0},
    }
    # the required list uses the alias, not the field name.
    assert schema["required"] == ["websiteUrl"]
