#!/usr/bin/env python
import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    if os.path.isfile("local_settings_test.py"):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testapp.local_settings_test")
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testapp.settings_test")
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["tests"])
    sys.exit(bool(failures))
