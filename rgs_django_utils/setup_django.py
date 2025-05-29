import logging
import os
import sys

import django
import dotenv


def setup_django(log: logging.Logger = None):
    """Setup django environment.

    :param log: logging Handler, which will be added to the stream handler (for debugging)
    :return:

    Example usage:

        if __name__ == '__main__':
            from rgs_utils.database.django_setup import setup_django
            setup_django()

        def example_function():
            pass

        if __name__ == '__main__':
            example_function()

    """
    root = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            os.pardir,
        )
    )
    print(root)
    sys.path.append(root)

    dotenv.load_dotenv(os.path.join(root, os.pardir, "waterworks/.env.dev"))

    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        raise Exception("DJANGO_SETTINGS_MODULE not set in .env.dev")
    # os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thissite.settings")

    django.setup()

    if log is not None:
        ch = logging.StreamHandler()
        log.addHandler(ch)
