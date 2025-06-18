import logging
import os
import sys
from pathlib import Path

import django
import dotenv


def check_env_file_has_param(env_file: Path, parameter: str) -> bool:
    """Check if the .env file has the parameter set.

    Params:
        env_file: path to the .env file
        parameter: parameter to check

    Returns:
        True if the parameter is set, False otherwise.
    """
    if not env_file.exists():
        return False

    with open(env_file, "r") as f:
        for line in f:
            if line.startswith(parameter):
                return True
    return False


def find_env_file_with_param(start_dir: Path, parameter: str, including_dev: bool = True) -> Path | None:
    """Recursively look in parent directories for a .env file (or .env.dev file if including_dev=True)
        with the parameter DJANGO_SETTINGS_MODULE set.
    Params:
        start_dir: directory to start searching from
        parameter: parameter to check in the .env file
        including_dev: if True, also check for .env.dev file
    Returns:
        Path to the .env file if found, None otherwise.
    """
    cur_dir = start_dir
    while True:
        env_file = Path(cur_dir, ".env")
        if Path(cur_dir, ".env").touch(exist_ok=True):
            if check_env_file_has_param(env_file, parameter):
                return env_file
        if including_dev:
            env_file_dev = Path(cur_dir, ".env.dev")
            if env_file_dev.touch(exist_ok=True):
                if check_env_file_has_param(env_file_dev, parameter):
                    return env_file_dev
        parent_dir = cur_dir.parent
        if parent_dir == cur_dir:  # reached the root directory
            break
        cur_dir = parent_dir

    return None


def find_settings_module_from_files(start_dir: Path) -> str | None:
    """Find the DJANGO_SETTINGS_MODULE from the directory structure (managed.py file and then subdirectorie with settings.py).

    Returns:
        str: the DJANGO_SETTINGS_MODULE path, e.g. 'thissite.settings'
    """
    cur_dir = start_dir
    while True:
        managed_py = Path(cur_dir, "manage.py")
        if managed_py.exists():
            # look for settings.py in the subdirectories
            for subdir in cur_dir.iterdir():
                if subdir.is_dir() and (subdir / "settings.py").exists():
                    return f"{subdir.name}.settings"
        parent_dir = cur_dir.parent
        if parent_dir == cur_dir:  # reached the root directory
            break
        cur_dir = parent_dir
    return None


def setup_django(from_env=False, log: logging.Logger = None):
    """Setup django environment.

    Example usage:

        if __name__ == '__main__':
            from rgs_django_utils.database.django_setup import setup_django
            setup_django()

        def example_function():
            pass

        if __name__ == '__main__':
            example_function()


    Params:
        root_dir: root_directory or sub directory.
        log: logging Handler, which will be added to the stream handler (for debugging)
    """

    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        pathname = Path(sys.argv[0]).parent

        if from_env:
            env_file = find_env_file_with_param(pathname, "DJANGO_SETTINGS_MODULE", including_dev=True)
            if env_file is not None:
                dotenv.load_dotenv(env_file)
            else:
                raise Exception(
                    "DJANGO_SETTINGS_MODULE not set and no .env file found with DJANGO_SETTINGS_MODULE parameter"
                )
        else:
            # if not from_env, we look for the directory with the managed.py file and look in de subdirectories for a settings.py file
            module_name = find_settings_module_from_files(pathname)
            if module_name is not None:
                os.environ["DJANGO_SETTINGS_MODULE"] = module_name
            else:
                raise Exception(
                    "DJANGO_SETTINGS_MODULE not set and no managed.py file found with settings.py in subdirectories"
                )
    # check if DJANGO_SETTINGS_MODULE is set
    if os.environ.get("DJANGO_SETTINGS_MODULE") is None:
        raise Exception("DJANGO_SETTINGS_MODULE not set in environment variables")

    django.setup()

    if log is not None:
        ch = logging.StreamHandler()
        log.addHandler(ch)
