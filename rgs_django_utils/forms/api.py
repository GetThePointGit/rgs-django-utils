import json
import logging
import os
from os import path

from core.rgs_django_workflow.tasks.api import GlobalError
from ninja import Body, Router
from thissite import settings

from rgs_django_utils.utils.authorization import JwtModuleToken

log = logging.getLogger(__name__)

form_api = Router(tags=["forms"])


@form_api.get(
    "/schema_json/models",
    response={200: dict, 401: GlobalError, 403: GlobalError, 500: GlobalError},
    auth=JwtModuleToken("admin"),  # super user
)
def get_schema_json_of_all_models(request):
    """Get the JSON schema of all models."""
    try:
        with open(path.join(settings.SCHEMA_ROOT, "datamodel.schema.json")) as f:
            json = f.read()
    except Exception:
        return 500, {"error": "Couldn't read schema json"}
    else:
        return 200, json


@form_api.get(
    "/schema_json/form/{str:model}",
    response={200: dict, 401: GlobalError, 403: GlobalError, 500: GlobalError},
    auth=JwtModuleToken("auth"),
)
def get_form_config_and_schema_json(request, model: str):
    """Get JSON schema and form configuration of a model."""
    # TODO: Deny certain models if organisation of user has no access to a module.
    try:
        with open(path.join(settings.SCHEMA_ROOT, "form", f"{model}.schema.json")) as f:
            model_schema = json.loads(f.read())
        with open(path.join(settings.SCHEMA_ROOT, "form", f"form_{model}.json")) as f:
            form_conf = json.loads(f.read())
    except Exception:
        return 500, {"error": "Couldn't read schema json"}
    else:
        return 200, {"model_schema": model_schema, "form_conf": form_conf}


@form_api.get(
    "/schema_json/form",
    response={200: dict, 401: GlobalError, 403: GlobalError, 500: GlobalError},
    auth=JwtModuleToken("admin"),  # super user
)
def get_form_config_and_schema_json_list(request):
    """Get list of available form models."""
    # TODO: Deny certain models if organisation of user has no access to a module.
    try:
        filenames = os.listdir(path.join(settings.SCHEMA_ROOT, "form"))
    except Exception:
        return 500, {"error": "Couldn't read schema json"}
    else:
        return 200, filenames


@form_api.post(
    "/schema_json/form/{str:model}",
    response={200: dict, 401: GlobalError, 403: GlobalError, 500: GlobalError},
    auth=JwtModuleToken("admin"),  # super user
)
def update_form_config_and_schema_json(request, model: str, item: dict = Body(...)):
    """Update JSON schema and form configuration of a model. This endpoint is intended to be used by the form builder in the frontend, not for general use."""
    try:
        json_schema = item.get("model_schema")
        form_conf = item.get("form_conf")
        if json_schema is None or form_conf is None:
            return 400, {"error": "model_schema and form_conf are required in the body."}
        with open(path.join(settings.SCHEMA_ROOT, "form", f"{model}.schema.json"), "w") as f:
            json.dump(json_schema, f)
        with open(path.join(settings.SCHEMA_ROOT, "form", f"form_{model}.json"), "w") as f:
            json.dump(form_conf, f)
    except Exception:
        return 500, {"error": "Couldn't write schema json"}
    else:
        return 200, {"message": "Form configuration saved successfully"}
