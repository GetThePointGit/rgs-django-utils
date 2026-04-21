import logging
import os

import dotenv

log = logging.getLogger("settings")


class SettingsGetter:
    """Layered settings reader — module attr → environment variable → default.

    Instances are typically created once in ``settings.py`` and reused for
    every ``get(...)`` call. Environment lookups are prefixed with a
    project-specific string so different apps on the same host don't clash.

    Parameters
    ----------
    local_settings : module
        Module where local settings are stored, for example an imported
        ``local_settings.py``.
    environment_setting_prefix : str, optional
        Prefix for environment variables (e.g. ``"APP_"`` so that
        ``DEBUG`` is read from ``APP_DEBUG``). Default is ``""`` (no prefix).
    default_warn_if_not_set : bool, optional
        If ``True``, log a warning the first time a setting is not found
        in any source. Per-call ``warn_if_not_set`` wins over this default.
        Default is ``True``.
    use_dotenv : bool, optional
        If ``True``, load ``.env`` on construction. Default is ``True``.
    dotenv_files : list of str or None, optional
        Explicit list of ``.env.*`` files to load (each one overrides
        already-set variables). When ``None`` a plain ``dotenv.load_dotenv()``
        is used. Default is ``None``.

    Examples
    --------
    >>> from types import ModuleType
    >>> local = ModuleType("local")
    >>> local.DEBUG = True
    >>> s = SettingsGetter(local, environment_setting_prefix="APP_", use_dotenv=False)
    >>> s.get("DEBUG")
    True
    >>> s.get("MISSING", default_value="fallback", warn_if_not_set=False)
    'fallback'
    """

    def __init__(
        self,
        local_settings,
        environment_setting_prefix="",
        default_warn_if_not_set=True,
        use_dotenv=True,
        dotenv_files=None,
    ):
        if use_dotenv:
            if dotenv_files is None:
                dotenv.load_dotenv()
            else:
                for dotenv_file in dotenv_files:
                    dotenv.load_dotenv(dotenv_file, override=True)

        self.local_settings = local_settings
        self.environment_setting_prefix = environment_setting_prefix
        self.default_warn_if_not_set = default_warn_if_not_set

    def get(self, name: str, default_value=None, split_by: str = None, warn_if_not_set: bool = None):
        """Resolve a setting from the layered sources.

        Lookup order:

        1. Attribute on ``local_settings``.
        2. Environment variable ``{environment_setting_prefix}{name}``.
        3. ``default_value``.

        When reading from the environment, the raw string is coerced to
        ``bool`` if ``default_value`` is a bool, or split on ``split_by``
        when that argument is given.

        Parameters
        ----------
        name : str
            Setting name (without prefix).
        default_value : Any, optional
            Returned when the setting is missing in all sources. Its type
            also drives environment-variable coercion (``bool`` → parsed).
        split_by : str, optional
            Split the environment-variable string on this delimiter and
            return a list. Ignored when reading from ``local_settings``.
        warn_if_not_set : bool, optional
            Override the instance-level ``default_warn_if_not_set`` for
            this call.

        Returns
        -------
        Any
            The resolved value, or ``default_value`` if not found.
        """
        if hasattr(self.local_settings, name):
            return getattr(self.local_settings, name)

        environment_param = self.environment_setting_prefix + name

        if environment_param in os.environ:
            value = os.environ.get(environment_param)
            if isinstance(default_value, bool):
                return value.lower() in ("true", "1", 1)
            if split_by:
                return value.split(split_by)
            return value

        if default_value in [None, ""]:
            if warn_if_not_set is None:
                warn_if_not_set = self.default_warn_if_not_set
            if warn_if_not_set:
                log.warning(f'"{name}" not set in local_settings.py or environment')
            else:
                log.debug(f'"{name}" not set in local_settings.py or environment')

        return default_value
