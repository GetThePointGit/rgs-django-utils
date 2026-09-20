"""Tests voor het behoud van FK-deferrability in
``install_db_defaults_and_relation_cascading``.

De functie herschrijft elke FK-constraint met ``on_delete``
CASCADE/SET_NULL/SET_DEFAULT als ``DEFERRABLE``. Vóór de fix werd de
``INITIALLY``-status daarbij altijd naar ``IMMEDIATE`` gezet, ook als een
migratie bewust ``INITIALLY DEFERRED`` had ingesteld. Deze tests zetten dat
scenario op met een echte Postgres-verbinding.
"""

import pytest
from django.db import connection
from psycopg import sql

from rgs_django_utils.database.install_db_defaults_and_relation_cascading import (
    install_db_defaults_and_relation_cascading,
)
from tests.testapp.models import ChildModel


def _fk_constraint(cursor, table, column):
    """Zoek de deferred-instellingen op van de FK-constraint op ``table.column``.

    Parameters
    ----------
    cursor : django.db.backends.utils.CursorWrapper
        Open databasecursor.
    table : str
        Ongekwalificeerde tabelnaam (gezocht in het ``public``-schema).
    column : str
        Kolom die de foreign key draagt.

    Returns
    -------
    tuple[str, bool, bool]
        ``(constraint_naam, condeferrable, condeferred)``.
    """
    cursor.execute(
        """
        SELECT c.conname, c.condeferrable, c.condeferred
        FROM pg_attribute a
        JOIN pg_constraint c ON (c.conrelid, c.conkey[1]) = (a.attrelid, a.attnum)
        WHERE c.contype = 'f'
          AND a.attrelid = %(table)s::regclass
          AND a.attname = %(column)s
        """,
        {"table": f"public.{table}", "column": column},
    )
    return cursor.fetchone()


@pytest.mark.django_db(transaction=True)
def test_install_db_defaults_preserves_initially_deferred():
    """Een bestaande ``INITIALLY DEFERRED``-constraint overleeft de herschrijving.

    Django zelf maakt FK-constraints op Postgres al ``DEFERRABLE INITIALLY
    DEFERRED`` aan bij een verse ``migrate`` (versie-afhankelijk), dus de
    testopzet zet de beginstaat van beide constraints expliciet met
    ``ALTER CONSTRAINT`` — onafhankelijk van dat gedrag.

    ``ChildModel.set_null_parent`` wordt op ``DEFERRABLE INITIALLY DEFERRED``
    gezet, zoals een migratie in een consumerend project (waterworks) doet
    voor een FK die in willekeurige volgorde binnen één transactie moet
    kunnen worden ingevuld. ``ChildModel.middle_model`` wordt op
    ``DEFERRABLE INITIALLY IMMEDIATE`` gezet. Na
    ``install_db_defaults_and_relation_cascading`` moeten beide FK's nog
    steeds deferrable zijn (bestaand gedrag), maar moet alleen hun
    ``INITIALLY``-status ongewijzigd zijn gebleven — vóór de fix werd die
    van de eerste FK stilzwijgend teruggezet naar ``IMMEDIATE``.
    """
    db_table = ChildModel._meta.db_table
    deferred_column = ChildModel._meta.get_field("set_null_parent").column
    immediate_column = ChildModel._meta.get_field("middle_model").column

    with connection.cursor() as cursor:
        deferred_name, _, _ = _fk_constraint(cursor, db_table, deferred_column)
        immediate_name, _, _ = _fk_constraint(cursor, db_table, immediate_column)

        cursor.execute(
            sql.SQL("ALTER TABLE {table} ALTER CONSTRAINT {name} DEFERRABLE INITIALLY DEFERRED;").format(
                table=sql.Identifier(db_table), name=sql.Identifier(deferred_name)
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table} ALTER CONSTRAINT {name} DEFERRABLE INITIALLY IMMEDIATE;").format(
                table=sql.Identifier(db_table), name=sql.Identifier(immediate_name)
            )
        )

        _, deferrable_before, deferred_before = _fk_constraint(cursor, db_table, deferred_column)
        assert (deferrable_before, deferred_before) == (True, True), "test-aanname: baseline niet zoals verwacht"
        _, immediate_deferrable_before, immediate_deferred_before = _fk_constraint(cursor, db_table, immediate_column)
        assert (immediate_deferrable_before, immediate_deferred_before) == (
            True,
            False,
        ), "test-aanname: baseline niet zoals verwacht"

    install_db_defaults_and_relation_cascading()

    with connection.cursor() as cursor:
        _, deferrable_after, deferred_after = _fk_constraint(cursor, db_table, deferred_column)
        assert deferrable_after is True
        assert deferred_after is True, "INITIALLY DEFERRED moet overleven"

        _, immediate_deferrable_after, immediate_deferred_after = _fk_constraint(cursor, db_table, immediate_column)
        assert immediate_deferrable_after is True
        assert immediate_deferred_after is False, "expliciet IMMEDIATE gezette FK blijft IMMEDIATE"
