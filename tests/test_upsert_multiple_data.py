"""Tests voor de json-afhandeling in ``upsert_multiple_data``.

psycopg3 kent geen dumper voor ``dict``/``list``; zonder wrapper faalt de
``cursor.mogrify`` in ``upsert_multiple_data`` op elke rij met een json-waarde.
"""

import pytest
from psycopg.adapt import PyFormat, Transformer
from psycopg.errors import ProgrammingError
from psycopg.types.json import Jsonb

from rgs_django_utils.database.upsert_multiple_data import (
    _get_json_column_wrappers,
    _wrap_json_values,
)
from tests.testapp.models import ChildModel


def _dump(value):
    """Dump *value* zoals psycopg3 dat in een TEXT-placeholder doet."""
    return Transformer().get_dumper(value, PyFormat.TEXT).dump(value)


def test_json_column_wrappers_only_for_json_columns():
    wrappers = _get_json_column_wrappers(["ids", "int_field", "json_field"], ChildModel)

    assert wrappers == {2: Jsonb}


def test_json_column_wrappers_empty_without_json_columns():
    assert _get_json_column_wrappers(["ids", "int_field"], ChildModel) == {}


def test_wrap_json_values_wraps_dict_and_list():
    row = ["a", 1, {"criteria": []}]
    wrappers = {2: Jsonb}

    assert isinstance(_wrap_json_values(row, wrappers)[2], Jsonb)

    row = ["a", 1, [{"id": "d_max"}]]
    assert isinstance(_wrap_json_values(row, wrappers)[2], Jsonb)


def test_wrap_json_values_leaves_none_and_str_alone():
    # None moet NULL blijven; een str is door de aanroeper al geserialiseerd
    # (json.dumps) en wordt door Postgres zelf naar jsonb gecast.
    assert _wrap_json_values(["a", 1, None], {2: Jsonb})[2] is None
    assert _wrap_json_values(["a", 1, '{"a": 1}'], {2: Jsonb})[2] == '{"a": 1}'


def test_bare_dict_cannot_be_dumped_but_wrapped_dict_can():
    # Dit is de fout die het wikkelen voorkomt:
    # "cannot adapt type 'dict' using placeholder '%t' (format: TEXT)".
    with pytest.raises(ProgrammingError):
        _dump({"fail_class": 50})

    row = _wrap_json_values(["a", 1, {"fail_class": 50}], {2: Jsonb})

    assert _dump(row[2]) == b'{"fail_class": 50}'
