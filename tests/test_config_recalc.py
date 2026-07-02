"""Tests voor de ``recalc``-parameter op ``Config``."""

from rgs_django_utils.database.dj_extended_models import Config


def test_config_recalc_default_none():
    assert Config().recalc is None


def test_config_recalc_stores_targets():
    assert Config(recalc=["pm", "project"]).recalc == ["pm", "project"]
