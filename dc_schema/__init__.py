from __future__ import annotations

import datetime
import enum
import dataclasses
import numbers
import types
import typing as t

_MISSING = dataclasses.MISSING


def get_schema(dc):
    return _GetSchema()(dc)


_Format = t.Literal[
    "date-time",
    "time",
    "date",
    "duration",
    "email",
    "idn-email",
    "hostname",
    "idn-hostname",
    "ipv4",
    "ipv6",
    "uuid",
    "uri",
    "uri-reference",
    "iri",
    "iri-reference",
]


@dataclasses.dataclass(frozen=True)
class SchemaAnnotation:
    # `alias` is a directive, not a schema keyword: it overrides the property
    # name a field takes in its dataclass's `properties` (and `required`), and
    # the serialised key `to_dict`/`from_dict` use. It is excluded from
    # `schema()` so it never leaks into the field's schema body.
    alias: t.Optional[str] = None
    # `additional_properties` closes (or shapes) an object body: `False` forbids
    # extra properties, `True` allows any, and a type generates a subschema each
    # extra property must validate against (2020-12's `additionalProperties`
    # takes a schema, not just a boolean). It is a body concern, so it is
    # excluded from `schema()` and consumed by `create_dc_schema`, never emitted
    # as a `$ref` sibling. Set it via a dataclass's `SchemaConfig.annotation`.
    additional_properties: t.Union[bool, type, None] = None
    title: t.Optional[str] = None
    description: t.Optional[str] = None
    examples: t.Optional[list[t.Any]] = None
    deprecated: t.Optional[bool] = None
    min_length: t.Optional[int] = None
    max_length: t.Optional[int] = None
    pattern: t.Optional[str] = None
    # Any string: `format` is an open, annotation-only keyword in 2020-12, so
    # custom/unimplemented values (e.g. "uri-template", "byte") pass through.
    # `_Format` lists the standard values for reference.
    format: t.Optional[str] = None
    minimum: t.Optional[numbers.Number] = None
    maximum: t.Optional[numbers.Number] = None
    exclusive_minimum: t.Optional[numbers.Number] = None
    exclusive_maximum: t.Optional[numbers.Number] = None
    multiple_of: t.Optional[numbers.Number] = None
    min_items: t.Optional[int] = None
    max_items: t.Optional[int] = None
    unique_items: t.Optional[bool] = None

    def schema(self):
        key_map = {
            "min_length": "minLength",
            "max_length": "maxLength",
            "exclusive_minimum": "exclusiveMinimum",
            "exclusive_maximum": "exclusiveMaximum",
            "multiple_of": "multipleOf",
            "min_items": "minItems",
            "max_items": "maxItems",
            "unique_items": "uniqueItems",
        }
        directives = ("alias", "additional_properties")
        return {
            key_map.get(k, k): v
            for k, v in dataclasses.asdict(self).items()
            if v is not None and k not in directives
        }


class _GetSchema:
    def __call__(self, dc):
        self.root = dc
        self.seen_root = False

        self.defs = {}
        schema = self.get_dc_schema(dc, SchemaAnnotation())
        if self.defs:
            schema["$defs"] = self.defs

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **schema,
        }

    def get_dc_schema(self, dc, annotation):
        # 2020-12 allows keywords beside `$ref`, so a bare `$ref` (plus any
        # annotation keywords) suffices -- no draft-7 `allOf` wrapper needed.
        if dc == self.root:
            if self.seen_root:
                return {"$ref": "#", **annotation.schema()}
            else:
                self.seen_root = True
                schema = self.create_dc_schema(dc)
                return schema
        else:
            if dc.__name__ not in self.defs:
                schema = self.create_dc_schema(dc)
                self.defs[dc.__name__] = schema
            return {"$ref": f"#/$defs/{dc.__name__}", **annotation.schema()}

    def create_dc_schema(self, dc):
        if hasattr(dc, "SchemaConfig"):
            annotation = getattr(
                dc.SchemaConfig, "annotation", SchemaAnnotation()
            )
        else:
            annotation = SchemaAnnotation()
        schema = {
            "type": "object",
            "title": dc.__name__,
            **annotation.schema(),
            "properties": {},
            "required": [],
        }
        type_hints = t.get_type_hints(dc, include_extras=True)
        for field in dataclasses.fields(dc):
            type_ = type_hints[field.name]
            name = self.property_name(field.name, type_)
            schema["properties"][name] = self.get_field_schema(
                type_, field.default, SchemaAnnotation()
            )
            field_is_optional = (
                field.default is not _MISSING
                or field.default_factory is not _MISSING
            )
            if not field_is_optional:
                schema["required"].append(name)
        if not schema["required"]:
            schema.pop("required")
        if annotation.additional_properties is not None:
            schema["additionalProperties"] = self.additional_properties_schema(
                annotation.additional_properties
            )
        return schema

    def additional_properties_schema(self, additional_properties):
        # `True`/`False` are literal schemas; a type generates the subschema
        # that every extra property must validate against.
        if isinstance(additional_properties, bool):
            return additional_properties
        return self.get_field_schema(
            additional_properties, _MISSING, SchemaAnnotation()
        )

    def property_name(self, name, type_):
        # A field may alias its property name via SchemaAnnotation(alias=...) in
        # its Annotated metadata; otherwise the field name is used verbatim.
        if t.get_origin(type_) is t.Annotated:
            meta = t.get_args(type_)[1]
            if isinstance(meta, SchemaAnnotation) and meta.alias is not None:
                return meta.alias
        return name

    def get_field_schema(self, type_, default, annotation):
        if dataclasses.is_dataclass(type_):
            return self.get_dc_schema(type_, annotation)
        if type_ is t.Any:
            return self.get_any_schema(default, annotation)
        if type_ is object:
            raise TypeError(
                "bare `object` is ambiguous for JSON Schema: use `typing.Any` "
                "for any JSON value, or `dict` for a JSON object"
            )
        if t.get_origin(type_) in (t.Union, types.UnionType):
            return self.get_union_schema(type_, default, annotation)
        if t.get_origin(type_) == t.Literal:
            return self.get_literal_schema(type_, default, annotation)
        if t.get_origin(type_) == t.Annotated:
            return self.get_annotated_schema(type_, default)
        elif type_ == dict or t.get_origin(type_) == dict:
            return self.get_dict_schema(type_, annotation)
        elif type_ == list or t.get_origin(type_) == list:
            return self.get_list_schema(type_, annotation)
        elif type_ == tuple or t.get_origin(type_) == tuple:
            return self.get_tuple_schema(type_, default, annotation)
        elif type_ == set or t.get_origin(type_) == set:
            return self.get_set_schema(type_, annotation)
        elif type_ is None or type_ == type(None):
            return self.get_none_schema(default, annotation)
        elif type_ == str:
            return self.get_str_schema(default, annotation)
        elif type_ == bool:
            return self.get_bool_schema(default, annotation)
        elif type_ == int:
            return self.get_int_schema(default, annotation)
        elif issubclass(type_, numbers.Number):
            return self.get_number_schema(default, annotation)
        elif issubclass(type_, enum.Enum):
            return self.get_enum_schema(type_, default, annotation)
        elif issubclass(type_, datetime.datetime):
            return self.get_datetime_schema(annotation)
        elif issubclass(type_, datetime.date):
            return self.get_date_schema(annotation)
        else:
            raise NotImplementedError(f"field type '{type_}' not implemented")

    def get_union_schema(self, type_, default, annotation):
        arms = [
            self.get_field_schema(arg, _MISSING, SchemaAnnotation())
            for arg in t.get_args(type_)
        ]
        body = self.collapse_nullable(arms, annotation)
        if default is _MISSING:
            return {**body, **annotation.schema()}
        return {**body, "default": default, **annotation.schema()}

    def collapse_nullable(self, arms, annotation):
        # A single concrete type plus None reads better as a `type` array --
        # {"type": ["integer", "null"]} -- than as a two-branch anyOf, and it
        # yields a smaller validation error. Collapse only when nothing else
        # needs a home: the concrete arm is a bare {"type": <name>}, and the
        # field carries no annotation that would attach to one of the arms.
        # Otherwise keep the explicit anyOf, where each arm owns its keywords.
        concrete = [arm for arm in arms if arm != {"type": "null"}]
        nullable = len(concrete) < len(arms)
        collapsible = (
            nullable
            and len(concrete) == 1
            and list(concrete[0]) == ["type"]
            and isinstance(concrete[0]["type"], str)
            and not annotation.schema()
        )
        if collapsible:
            return {"type": [concrete[0]["type"], "null"]}
        return {"anyOf": arms}

    def get_literal_schema(self, type_, default, annotation):
        if default is _MISSING:
            schema = {**annotation.schema()}
        else:
            schema = {"default": default, **annotation.schema()}
        args = t.get_args(type_)
        return {"enum": list(args), **schema}

    def get_dict_schema(self, type_, annotation):
        args = t.get_args(type_)
        assert len(args) in (0, 2)
        if args:
            assert args[0] == str
            return {
                "type": "object",
                "additionalProperties": self.get_field_schema(
                    args[1], _MISSING, SchemaAnnotation()
                ),
                **annotation.schema(),
            }
        else:
            return {"type": "object", **annotation.schema()}

    def get_list_schema(self, type_, annotation):
        args = t.get_args(type_)
        assert len(args) in (0, 1)
        if args:
            return {
                "type": "array",
                "items": self.get_field_schema(
                    args[0], _MISSING, SchemaAnnotation()
                ),
                **annotation.schema(),
            }
        else:
            return {"type": "array", **annotation.schema()}

    def get_tuple_schema(self, type_, default, annotation):
        if default is _MISSING:
            schema = {**annotation.schema()}
        else:
            schema = {"default": list(default), **annotation.schema()}
        args = t.get_args(type_)
        if args and len(args) == 2 and args[1] is ...:
            schema = {
                "type": "array",
                "items": self.get_field_schema(
                    args[0], _MISSING, SchemaAnnotation()
                ),
                **schema,
            }
        elif args:
            schema = {
                "type": "array",
                "prefixItems": [
                    self.get_field_schema(arg, _MISSING, SchemaAnnotation())
                    for arg in args
                ],
                "minItems": len(args),
                "maxItems": len(args),
                **schema,
            }
        else:
            schema = {"type": "array", **schema}
        return schema

    def get_set_schema(self, type_, annotation):
        args = t.get_args(type_)
        assert len(args) in (0, 1)
        if args:
            return {
                "type": "array",
                "items": self.get_field_schema(
                    args[0], _MISSING, SchemaAnnotation()
                ),
                "uniqueItems": True,
                **annotation.schema(),
            }
        else:
            return {"type": "array", "uniqueItems": True, **annotation.schema()}

    def get_any_schema(self, default, annotation):
        # `typing.Any`: an empty schema accepts any JSON value.
        if default is _MISSING:
            return {**annotation.schema()}
        return {"default": default, **annotation.schema()}

    def get_none_schema(self, default, annotation):
        if default is _MISSING:
            return {"type": "null", **annotation.schema()}
        else:
            return {"type": "null", "default": default, **annotation.schema()}

    def get_str_schema(self, default, annotation):
        if default is _MISSING:
            return {"type": "string", **annotation.schema()}
        else:
            return {"type": "string", "default": default, **annotation.schema()}

    def get_bool_schema(self, default, annotation):
        if default is _MISSING:
            return {"type": "boolean", **annotation.schema()}
        else:
            return {
                "type": "boolean",
                "default": default,
                **annotation.schema(),
            }

    def get_int_schema(self, default, annotation):
        if default is _MISSING:
            return {"type": "integer", **annotation.schema()}
        else:
            return {
                "type": "integer",
                "default": default,
                **annotation.schema(),
            }

    def get_number_schema(self, default, annotation):

        if default is _MISSING:
            return {"type": "number", **annotation.schema()}
        else:
            return {"type": "number", "default": default, **annotation.schema()}

    def get_enum_schema(self, type_, default, annotation):
        if type_.__name__ not in self.defs:
            self.defs[type_.__name__] = {
                "title": type_.__name__,
                "enum": [v.value for v in type_],
            }
        if default is _MISSING:
            return {"$ref": f"#/$defs/{type_.__name__}", **annotation.schema()}
        else:
            return {
                "$ref": f"#/$defs/{type_.__name__}",
                "default": default.value,
                **annotation.schema(),
            }

    def get_annotated_schema(self, type_, default):
        args = t.get_args(type_)
        assert len(args) == 2
        return self.get_field_schema(args[0], default, args[1])

    def get_datetime_schema(self, annotation):
        return {"type": "string", "format": "date-time", **annotation.schema()}

    def get_date_schema(self, annotation):
        return {"type": "string", "format": "date", **annotation.schema()}


# --- data serde -------------------------------------------------------------
# The other direction of the dataclass<->JSON bridge: convert dataclass
# instances to and from JSON-ready dicts, honouring the same
# `SchemaAnnotation(alias=...)` aliases the schema uses for property names. This
# is generic -- no MCP knowledge -- and driven by the annotations defined above.


def to_dict(instance: t.Any) -> t.Any:
    """Render a dataclass (or a tree of them) as a JSON-ready value.

    Each field is emitted under its `SchemaAnnotation(alias=...)` alias (else the
    field name), recursing into nested dataclasses, `list`/`tuple`, `dict`, and
    `enum.Enum`; scalars pass through. `None`-valued fields are omitted -- an
    absent key, never a literal `null`. The inverse is `from_dict`.
    """
    if dataclasses.is_dataclass(instance) and not isinstance(instance, type):
        return _dataclass_to_dict(instance)
    if isinstance(instance, (list, tuple)):
        return [to_dict(item) for item in instance]
    if isinstance(instance, dict):
        return {key: to_dict(value) for key, value in instance.items()}
    if isinstance(instance, enum.Enum):
        return instance.value
    return instance


def _dataclass_to_dict(instance):
    hints = t.get_type_hints(type(instance), include_extras=True)
    result = {}
    for field in dataclasses.fields(instance):
        value = getattr(instance, field.name)
        if value is None:  # optional -> omitted, never a literal null
            continue
        result[_alias(field.name, hints[field.name])] = to_dict(value)
    return result


def _alias(name, hint):
    # A field aliases its serialised name via SchemaAnnotation(alias=...) in its
    # Annotated metadata; otherwise the field name is used verbatim. (The schema
    # side reads the same alias in `_GetSchema.property_name`.)
    if t.get_origin(hint) is t.Annotated:
        meta = t.get_args(hint)[1]
        if isinstance(meta, SchemaAnnotation) and meta.alias is not None:
            return meta.alias
    return name


def from_dict(cls: type, data: dict) -> t.Any:
    """Reconstruct a `cls` dataclass instance from a JSON-ready dict.

    The inverse of `to_dict`: each key is matched back to its field by the
    field's `SchemaAnnotation(alias=...)` alias (else the field name), and values
    are reconstructed by field type (nested dataclasses, `list`s, `dict`s,
    enums, `X | None`). An omitted key leaves the field's default. `from_dict`
    trusts the shape of `data` -- it builds, it does not validate.
    """
    return _dataclass_from_dict(cls, data)


def _dataclass_from_dict(cls, data):
    hints = t.get_type_hints(cls, include_extras=True)
    arguments = {}
    for field in dataclasses.fields(cls):
        alias = _alias(field.name, hints[field.name])
        if alias in data:  # absent -> the field's default applies
            arguments[field.name] = _value_from_dict(
                hints[field.name], data[alias]
            )
    return cls(**arguments)


def _value_from_dict(hint, value):
    hint = _strip_annotated(hint)
    if dataclasses.is_dataclass(hint) and isinstance(hint, type):
        return _dataclass_from_dict(hint, value)
    origin = t.get_origin(hint)
    if origin is list:
        args = t.get_args(hint)
        item_hint = args[0] if args else t.Any
        return [_value_from_dict(item_hint, item) for item in value]
    if origin is dict:
        args = t.get_args(hint)
        value_hint = args[1] if args else t.Any
        return {
            key: _value_from_dict(value_hint, item)
            for key, item in value.items()
        }
    if origin is t.Union or origin is types.UnionType:
        return _union_from_dict(hint, value)
    if isinstance(hint, type) and issubclass(hint, enum.Enum):
        return hint(value)
    return value


def _union_from_dict(hint, value):
    if value is None:
        return None
    concrete = [arm for arm in t.get_args(hint) if arm is not type(None)]
    if len(concrete) == 1:  # `X | None` -> reconstruct as X
        return _value_from_dict(concrete[0], value)
    # Several concrete arms carry no discriminator to pick a target by; pass
    # such values through untouched (the shape is trusted).
    return value


def _strip_annotated(hint):
    if t.get_origin(hint) is t.Annotated:
        return t.get_args(hint)[0]
    return hint
