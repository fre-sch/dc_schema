# dc_schema

Tiny library to generate [JSON schema](https://json-schema.org/) (2020-12) from python
[dataclasses](https://docs.python.org/3/library/dataclasses.html). No other dependencies, standard library only.

> [!NOTE]
> Fork of [Peter554/dc_schema](https://github.com/Peter554/dc_schema)
> This is a **scratch-your-own-itch project**, meaning
> - Consider this experimental
> - No release to https://pypi.org/
> - I don't intend to become a maintainer, that's not the kind of itch I want
>   to scratch here.
> - Use the git+https URL to install
> - Want to become a maintainer? Fork or copy it, maintain it. See LICENSE.

## Install

```
pip install 'dc_schema @ git+https://github.com/fre-sch/dc_schema@master'
```

## Assumptions

* python 3.12+

## Motivation

Create a lightweight, focused solution to generate JSON schema from plain
dataclasses. [pydantic](https://pydantic-docs.helpmanual.io/) is a much more
mature option, however it also does a lot of other things that aren't included
here.

## Usage

### Basics

Create a regular python dataclass and pass it to `get_schema`.

```py
import dataclasses
import datetime
import json

from dc_schema import get_schema

@dataclasses.dataclass
class Book:
    title: str
    published: bool = False

@dataclasses.dataclass
class Author:
    name: str
    age: int
    dob: datetime.date
    books: list[Book]

print(json.dumps(get_schema(Author), indent=2))
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "title": "Author",
  "properties": {
    "name": {
      "type": "string"
    },
    "age": {
      "type": "integer"
    },
    "dob": {
      "type": "string",
      "format": "date"
    },
    "books": {
      "type": "array",
      "items": {
        "allOf": [
          {
            "$ref": "#/$defs/Book"
          }
        ]
      }
    }
  },
  "required": [
    "name",
    "age",
    "dob",
    "books"
  ],
  "$defs": {
    "Book": {
      "type": "object",
      "title": "Book",
      "properties": {
        "title": {
          "type": "string"
        },
        "published": {
          "type": "boolean",
          "default": false
        }
      },
      "required": [
        "title"
      ]
    }
  }
}
```

### Instances to and from dicts

Where `get_schema` describes the shape, `to_dict` and `from_dict` move the data:
convert a dataclass instance to a JSON-ready `dict` and reconstruct it again.
Both are the inverse of each other and recurse through nested dataclasses,
`list`/`tuple`/`set`/`frozenset`, `dict`, and `enum.Enum`.

```py
from dc_schema import to_dict, from_dict

book = Book(title="A Wizard of Earthsea", published=True)

data = to_dict(book)
print(data)  # {'title': 'A Wizard of Earthsea', 'published': True}

restored = from_dict(Book, data)
print(restored)  # Book(title='A Wizard of Earthsea', published=True)
```

* `None`-valued fields are omitted rather than written as a literal `null`, so an
absent key falls back to the field's default on the way back in.
* `SchemaAnnotation(alias=...)` is respected to convert dict key names. Use
`to_dict(by_alias=False)` and `from_dict(by_alias=False)` to use the raw field names instead.
* Fields annotated with `datetime.date` and `datetime.datetime` are converted to and from RFC 3339 strings.
* `to_dict` converts `set` and `frozenset` to lists, `from_dict` iterates and
collects into the annotated type.
* `from_dict` trusts the shape of its input: it builds, it does not validate.

### Annotations

You can use [typing.Annotated](https://docs.python.org/3/library/typing.html#typing.Annotated) + `SchemaAnnotation`
to attach metadata to the schema, such as field descriptions, examples,
validation (min/max length, regex pattern, ...), etc. Consult
[the code](https://github.com/Peter554/dc_schema/blob/master/dc_schema/__init__.py)
for full details.

```py
import dataclasses
import datetime
import json
import typing as t

from dc_schema import get_schema, SchemaAnnotation

@dataclasses.dataclass
class Author:
    name: t.Annotated[
        str,
        SchemaAnnotation(title="Full name", description="The authors full name")
    ]
    age: t.Annotated[int, SchemaAnnotation(minimum=0)]
    dob: t.Annotated[
        t.Optional[datetime.date],
        SchemaAnnotation(examples=["1990-01-17"])
    ] = None

print(json.dumps(get_schema(Author), indent=2))
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "title": "Author",
  "properties": {
    "name": {
      "type": "string",
      "title": "Full name",
      "description": "The authors full name"
    },
    "age": {
      "type": "integer",
      "minimum": 0
    },
    "dob": {
      "anyOf": [
        {
          "type": "string",
          "format": "date"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "examples": [
        "1990-01-17"
      ]
    }
  },
  "required": [
    "name",
    "age"
  ]
}
```

`SchemaAnnotation` takes keyword arguments only.

### Choices

`Choices` declares a set of string choices inline at the field. 
A mapping emits `{const, title}`, a sequence emits a plain `enum`. Cardinality 
comes from the *container*: a `str` becomes one `oneOf`, a `list[str]` becomes `anyOf`.

`Choices` is a `SchemaAnnotation`, so it carries `description`, `title`,
`min_items`, `alias` and the rest itself -- the choices are the one positional
argument, everything else stays keyword.

```py
import dataclasses
import json
import typing as t

from dc_schema import get_schema, Choices

@dataclasses.dataclass
class PizzaOrder:
    dough: t.Annotated[
        str,
        Choices({"thin": "Thin & Crispy", "deep-dish": "Chicago Deep Dish"},
                description="How the base is made.")
    ]
    toppings: t.Annotated[list[str], Choices(["pepperoni", "mushroom"])]

print(json.dumps(get_schema(PizzaOrder), indent=2))
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "title": "PizzaOrder",
  "properties": {
    "dough": {
      "type": "string",
      "oneOf": [
        {
          "const": "thin",
          "title": "Thin & Crispy"
        },
        {
          "const": "deep-dish",
          "title": "Chicago Deep Dish"
        }
      ],
      "description": "How the base is made."
    },
    "toppings": {
      "type": "array",
      "items": {
        "enum": [
          "pepperoni",
          "mushroom"
        ]
      }
    }
  },
  "required": [
    "dough",
    "toppings"
  ]
}
```

Choice values must be strings, and must be distinct -- two branches sharing a
`const` would make a value valid under both, so `oneOf` would reject a legal
value. Both are checked when the `Choices` is constructed.

`Choices` emits inline schema, not `$defs` + `$ref`.

### `dataclass` Metadata
To customize the metadata of a dataclass itself, use a `SchemaConfig`. The
class-level `description` is taken only from here -- `get_schema` never reads the
class docstring -- so a schema description is always an explicit choice, kept
distinct from the docstring that documents the dataclass in code.

```py
import dataclasses
import json

from dc_schema import get_schema, SchemaAnnotation

@dataclasses.dataclass
class User:
    name: str

    class SchemaConfig:
        annotation = SchemaAnnotation(
            title="System user",
            description="A user of the system"
        )

print(json.dumps(get_schema(User), indent=2))
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "title": "System user",
  "description": "A user of the system",
  "properties": {
    "name": {
      "type": "string"
    }
  },
  "required": [
    "name"
  ]
}
```

## CLI

```
dc_schema <file_path> <dataclass>
```

e.g.

```
dc_schema ./schema.py Author
```

## Other tools

For working with dataclasses or JSON schema:

* https://github.com/konradhalas/dacite - create data classes from dictionaries.
* https://python-jsonschema.readthedocs.io/en/stable/ - validate an object against a JSON schema.
* https://json-schema.org/understanding-json-schema/index.html - nice reference for understanding JSON schema.
