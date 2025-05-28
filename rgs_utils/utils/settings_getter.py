import os
import dotenv

import logging

log = logging.getLogger("settings")


class SettingsGetter:
    def __init__(self, local_settings, environment_setting_prefix="", default_warn_if_not_set=True, use_dotenv=True):
        if use_dotenv:
            dotenv.load_dotenv()

        self.local_settings = local_settings
        self.environment_setting_prefix = environment_setting_prefix
        self.default_warn_if_not_set = default_warn_if_not_set

    def get(self, name: str, default_value=None, split_by: str = None, warn_if_not_set: bool = None):
        """
        returns setting in the order of:
        - available in local_setting.py
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
