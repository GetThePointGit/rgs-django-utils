"""Genereer de plpgsql-functie die rol-id's omzet in Hasura-claims.

Hasura leest ``x-hasura-allowed-roles`` uit een JWT; die lijst komt uit een
gegenereerde kolom op een rij met rol-id's (bijvoorbeeld ``auth_org_member``).
De overerving tussen rollen staat in ``settings.PERMISSION_TREE``. Door de
plpgsql daaruit te renderen staat die graaf op één plek, in plaats van ook nog
eens met de hand in een ``IF``-keten in een migratie.
"""

from typing import Sequence

from rgs_django_utils.database.permission_helper import PermissionHelper

DEFAULT_BASE_ROLES = ("public", "auth", "user_self")


def _array_literal(roles: Sequence[str]) -> str:
    """Render een SQL-array-literal van rolnamen.

    Parameters
    ----------
    roles : sequence of str
        Rolnamen, in de volgorde waarin ze in de array moeten staan.

    Returns
    -------
    str
        Bijvoorbeeld ``ARRAY ['public', 'auth']``.
    """
    return "ARRAY [" + ", ".join(f"'{role}'" for role in roles) + "]"


def build_claim_function_sql(
    function_name: str,
    arguments: Sequence[str],
    base_roles: Sequence[str] = DEFAULT_BASE_ROLES,
) -> str:
    """Render een ``CREATE OR REPLACE FUNCTION`` voor de Hasura-claims.

    Voor elk argument — dat een rol-id bevat, of ``NULL`` — wordt een
    ``IF``/``ELSIF``-keten gerenderd over alle rollen uit
    ``settings.PERMISSION_TREE``. Elke tak voegt de volledige
    overervingsketen van die rol toe.

    De functie is ``IMMUTABLE`` en ``PARALLEL SAFE``, omdat hij gebruikt wordt
    in een ``GENERATED ... STORED``-kolom; Postgres weigert daar anders.

    Parameters
    ----------
    function_name : str
        Naam van de functie, zonder schema (die wordt ``public``).
    arguments : sequence of str
        Namen van de ``text``-argumenten, elk met een rol-id.
    base_roles : sequence of str, optional
        Rollen die iedereen krijgt, ongeacht de argumenten.

    Returns
    -------
    str
        De volledige plpgsql, klaar voor ``migrations.RunSQL``.
    """
    inheritance = PermissionHelper.get_permission_inherence_list()

    signature = ", ".join(f"{name} text" for name in arguments)
    lines = [
        f"CREATE OR REPLACE FUNCTION public.{function_name}({signature})",
        "  RETURNS TEXT[] AS -- allowed_roles",
        "$$",
        "DECLARE",
        "  role_set TEXT[];",
        "BEGIN",
        f"  role_set := {_array_literal(base_roles)};",
    ]

    for name in arguments:
        lines.append(f"  IF {name} IS NULL THEN")
        lines.append("    -- geen rol op dit argument; niets toevoegen")
        for role, chain in sorted(inheritance.items()):
            if role in base_roles:
                continue
            lines.append(f"  ELSIF {name} = '{role}' THEN")
            lines.append(f"    role_set := role_set || {_array_literal(chain)};")
        lines.append("  END IF;")

    lines += [
        "  role_set := (SELECT ARRAY(SELECT DISTINCT unnest(role_set)));",
        "  RETURN role_set;",
        "END;",
        "$$ LANGUAGE plpgsql",
        "  IMMUTABLE",
        "  PARALLEL SAFE;",
    ]
    return "\n".join(lines) + "\n"
