import logging
import os

import dotenv

log = logging.getLogger("settings")


class SettingsGetter:
    def __init__(
        self,
        local_settings,
        environment_setting_prefix="",
        default_warn_if_not_set=True,
        use_dotenv=True,
        dotenv_files=None,
    ):
        """Initialize the SettingsGetter.

        Arguments:
        ----------
        local_settings: module
            module where local settings are stored, for example an imported `local_settings.py`
        environment_setting_prefix: str
            prefix for environment variables, for example "APP_"
        default_warn_if_not_set: bool
            if True, a warning is logged when a setting is not found in local_settings or environment
        use_dotenv: bool
            if True, load environment variables from a .env file
        dotenv_files: list or None
            if provided, load environment variables from the specified .env.* files
        """
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
        """
        returns setting in the order of:
        - available in local_setting
        - available in environment with prefix ENVIRONMENT_SETTING_PREFIX
          for example APP_DEBUG ...
        - default
        """
        if hasattr(self.local_settings, name):
            return getattr(self.local_settings, name)

        environment_param = self.environment_setting_prefix + name

        if environment_param in os.environ:
            value = os.environ.get(environment_param)
            if type(default_value) == bool:
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
