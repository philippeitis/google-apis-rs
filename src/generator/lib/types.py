from random import randint, random, choice, seed

from .filters import camel_to_under
from .rust_type import Base, Option, Box, Vec, HashMap, RustType

seed(1337)

TREF = '$ref'
RESERVED_WORDS = set(('abstract', 'alignof', 'as', 'become', 'box', 'break', 'const', 'continue', 'crate', 'do',
                      'else', 'enum', 'extern', 'false', 'final', 'fn', 'for', 'if', 'impl', 'in', 'let', 'loop',
                      'macro', 'match', 'mod', 'move', 'mut', 'offsetof', 'override', 'priv', 'pub', 'pure', 'ref',
                      'return', 'sizeof', 'static', 'self', 'struct', 'super', 'true', 'trait', 'type', 'typeof',
                      'unsafe', 'unsized', 'use', 'virtual', 'where', 'while', 'yield'))

WORDS = [
    w.strip(',') for w in
    "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet.".split(
        ' ')]


def chrono_date(y=None, m=None, d=None):
    y = randint(1, 9999) if y is None else y
    m = randint(1, 12) if m is None else m
    d = randint(1, 31) if d is None else d
    return f"chrono::NaiveDate::from_ymd({y}, {m}, {d})"


CHRONO_PATH = "client::chrono"
CHRONO_DATETIME = f"{CHRONO_PATH}::DateTime<{CHRONO_PATH}::offset::Utc>"
CHRONO_DATE = f"{CHRONO_PATH}::NaiveDate"
USE_FORMAT = 'use_format_field'
CHRONO_UTC_NOW = "chrono::Utc::now()"

RUST_TYPE_MAP = {
    'boolean': Base("bool"),
    'integer': USE_FORMAT,
    'number': USE_FORMAT,
    'uint32': Base("u32"),
    'double': Base("f64"),
    'float': Base("f32"),
    'int32': Base("i32"),
    'any': Base("String"),  # TODO: Figure out how to handle it. It's 'interface' in Go ...
    'int64': Base("i64"),
    'uint64': Base("u64"),
    'array': Vec(None),
    'string': Base("String"),
    'object': HashMap(None, None),
    # https://github.com/protocolbuffers/protobuf/blob/ec1a70913e5793a7d0a7b5fbf7e0e4f75409dd41/src/google/protobuf/timestamp.proto
    # In JSON format, the Timestamp type is encoded as a string in the [RFC 3339] format
    'google-datetime': Base(CHRONO_DATETIME),
    # Per .json files: RFC 3339 timestamp
    'date-time': Base(CHRONO_DATETIME),
    # Per .json files: A date in RFC 3339 format with only the date part
    # e.g. "2013-01-15"
    'date': Base(CHRONO_DATE),
    # https://github.com/protocolbuffers/protobuf/blob/ec1a70913e5793a7d0a7b5fbf7e0e4f75409dd41/src/google/protobuf/duration.proto
    'google-duration': Base(f"{CHRONO_PATH}::Duration"),
    # guessing bytes is universally url-safe b64
    "byte": Vec(Base("u8")),
    # https://github.com/protocolbuffers/protobuf/blob/ec1a70913e5793a7d0a7b5fbf7e0e4f75409dd41/src/google/protobuf/field_mask.proto
    "google-fieldmask": Base("client::FieldMask")
}

RUST_TYPE_RND_MAP = {
    'bool': lambda: str(bool(randint(0, 1))).lower(),
    'u32': lambda: randint(0, 100),
    'u64': lambda: randint(0, 100),
    'f64': lambda: random(),
    'f32': lambda: random(),
    'i32': lambda: randint(-101, -1),
    'i64': lambda: randint(-101, -1),
    'String': lambda: '"%s"' % choice(WORDS),
    '&str': lambda: '"%s"' % choice(WORDS),
    '&Vec<String>': lambda: '&vec!["%s".into()]' % choice(WORDS),
    "Vec<u8>": lambda: f"vec![0, 1, 2, 3]",
    # why a reference to Vec? Because it works. Should be slice, but who knows how typing works here.
    "&Vec<u8>": lambda: f"&vec![0, 1, 2, 3]",
    # TODO: styling this
    f"{CHRONO_PATH}::Duration": lambda: f"chrono::Duration::seconds({randint(0, 9999999)})",
    CHRONO_DATE: chrono_date,
    CHRONO_DATETIME: lambda: CHRONO_UTC_NOW,
    "FieldMask": lambda: f"FieldMask(vec![{choice(WORDS)}])",
}

JSON_TO_RUST_DEFAULT = {
    'boolean': 'false',
    'uint32': '0',
    'uint64': '0',
    'int32': "-0",
    'int64': "-0",
    'float': '0.0',
    'double': '0.0',
    'string': "\"\"",
    'google-datetime': CHRONO_UTC_NOW,
    'date-time': CHRONO_UTC_NOW,
    'date': chrono_date(2000, 1, 1),
    # https://github.com/protocolbuffers/protobuf/blob/ec1a70913e5793a7d0a7b5fbf7e0e4f75409dd41/src/google/protobuf/duration.proto
    'google-duration': "chrono::Duration::seconds(0)",
    # guessing bytes is universally url-safe b64
    "byte": "b\"hello world\"",
    # https://github.com/protocolbuffers/protobuf/blob/ec1a70913e5793a7d0a7b5fbf7e0e4f75409dd41/src/google/protobuf/field_mask.proto
    "google-fieldmask": "FieldMask::default()"
}

assert set(JSON_TO_RUST_DEFAULT.keys()).issubset(set(RUST_TYPE_MAP.keys()))


# ==============================================================================
## @name Rust TypeSystem
# ------------------------------------------------------------------------------
## @{

def capitalize(s):
    return s[:1].upper() + s[1:]


# Return transformed string that could make a good type name
def canonical_type_name(s):
    # can't use s.capitalize() as it will lower-case the remainder of the string
    s = ''.join(capitalize(t) for t in s.split(' '))
    s = ''.join(capitalize(t) for t in s.split('_'))
    s = ''.join(capitalize(t) for t in s.split('-'))
    return capitalize(s)


def nested_type_name(sn, pn):
    suffix = canonical_type_name(pn)
    return sn + suffix


# Make properties which are reserved keywords usable
def mangle_ident(n):
    n = camel_to_under(n).replace('-', '.').replace('.', '_').replace('$', '')
    if n in RESERVED_WORDS:
        return n + '_'
    return n


def is_map_prop(p):
    return 'additionalProperties' in p


def _assure_unique_type_name(schemas, tn):
    if tn in schemas:
        tn += 'Nested'
        assert tn not in schemas
    return tn


# map a json type to a Rust type
# t = type dict
# NOTE: In case you don't understand how this algorithm really works ... me neither - THE AUTHOR
def to_rust_type(
        schemas,
        schema_name,
        property_name,
        t,
        allow_optionals=True,
        _is_recursive=False
) -> RustType:
    def nested_type(nt) -> RustType:
        if 'items' in nt:
            nt = nt['items']
        elif 'additionalProperties' in nt:
            nt = nt['additionalProperties']
        else:
            assert is_nested_type_property(nt)
            # It's a nested type - we take it literally like $ref, but generate a name for the type ourselves
            return Base(_assure_unique_type_name(schemas, nested_type_name(schema_name, property_name)))
        return to_rust_type(schemas, schema_name, property_name, nt, allow_optionals=False, _is_recursive=True)

    def wrap_type(rt) -> RustType:
        if allow_optionals:
            return Option(rt)
        return rt

    # unconditionally handle $ref types, which should point to another schema.
    if TREF in t:
        # simple, non-recursive fix for some recursive types. This only works on the first depth level
        # which is fine for now. 'allow_optionals' implicitly restricts type boxing for simple types - it
        # is usually on the first call, and off when recursion is involved.
        tn = t[TREF]
        rt = Base(tn)
        if not _is_recursive and tn == schema_name:
            rt = Option(Box(rt))
        return wrap_type(rt)
    try:
        # prefer format if present
        rust_type = RUST_TYPE_MAP[t.get("format", t["type"])]
        if rust_type == Vec(None):
            return wrap_type(Vec(nested_type(t)))
        if rust_type == HashMap(None, None):
            if is_map_prop(t):
                return wrap_type(HashMap(Base("String"), nested_type(t)))
            return wrap_type(nested_type(t))
        if t.get('repeated', False):
            return Vec(rust_type)
        return wrap_type(rust_type)
    except KeyError as err:
        raise AssertionError(
            "%s: Property type '%s' unknown - add new type mapping: %s" % (str(err), t['type'], str(t)))
    except AttributeError as err:
        raise AssertionError("%s: unknown dict layout: %s" % (str(err), t))


# return True if this property is actually a nested type
def is_nested_type_property(t):
    return 'type' in t and t['type'] == 'object' and 'properties' in t or ('items' in t and 'properties' in t['items'])


# Return True if the schema is nested
def is_nested_type(s):
    return len(s.parents) > 0


# given a rust type-name (no optional, as from to_rust_type), you will get a suitable random default value
# as string suitable to be passed as reference (or copy, where applicable)
def rnd_arg_val_for_type(tn):
    try:
        return str(RUST_TYPE_RND_MAP[str(tn)]())
    except KeyError:
        return '&Default::default()'
## -- End Rust TypeSystem -- @}
