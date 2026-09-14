from django.conf import settings

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.dj_extended_models import FieldActions


def base_model_role(name: str) -> str:
    """Translate a base-model role name into the project's own vocabulary.

    The abstract base models ship with role names from the project this
    library grew up in (``project_read``, ``project_edit``, ``proj_read``).
    Since role names are validated against ``settings.PERMISSION_TREE``, a
    project using a different vocabulary could not import the mixins at all.
    ``BASE_MODEL_ROLES`` maps the shipped name onto a name that project does
    have; without the setting every name maps onto itself, so existing
    consumers are unaffected.

    Parameters
    ----------
    name : str
        The role name as written in the base model.

    Returns
    -------
    str
        The project's own name for that role, or ``name`` unchanged when the
        project declares no mapping for it.

    Examples
    --------
    >>> base_model_role("project_read")  # doctest: +SKIP
    'aanvr_read'
    """
    return getattr(settings, "BASE_MODEL_ROLES", {}).get(name, name)


def audit_perm(edit: FieldActions = "isu") -> models.FPerm:
    """Field permissions for an audit column.

    Readable by organisation members and by whoever may read the record;
    writable by whoever may edit it. Which roles those are is up to the
    project — see :func:`base_model_role`.

    Parameters
    ----------
    edit : FieldActions, default "isu"
        What the editing role may do. The audit columns that are only set on
        insert pass ``"is-"``.

    Returns
    -------
    models.FPerm
        Permissions for one audit field.
    """
    return models.FPerm(
        **{
            "org_mem": "-s-",
            base_model_role("project_read"): "-s-",
            base_model_role("project_edit"): edit,
        }
    )
