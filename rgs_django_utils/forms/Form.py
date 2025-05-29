from typing import Any, Dict, Generator, List

import rgs_django_utils.logging as custom_logging
from rgs_django_utils.forms.fields.Field import Field, ValidationErrorMessage
from rgs_django_utils.forms.Section import Section
from rgs_django_utils.models.enums.message_code import EnumMessageCode
from rgs_django_utils.models.enums.source_type import EnumSourceType
from rgs_django_utils.models.task import WorkflowDataLog


def recursive_set_data(elements: List[Field | Section], data: Dict[str, Any]):
    for element in elements:
        if isinstance(element, Field):
            element.value = data.get(element.name, None)
        elif isinstance(element, Section):
            recursive_set_data(element.elements, data)


def recursive_get_value(elements: List[Field | Section]):
    out = {}
    for element in elements:
        if isinstance(element, Field):
            out[element.name] = element.value
        elif isinstance(element, Section):
            out.update(recursive_get_value(element.elements))
    return out


def recursive_validate(elements: List[Field | Section]) -> dict[str : list[ValidationErrorMessage]]:
    errors: dict[str : list[ValidationErrorMessage]] = {}
    for element in elements:
        if isinstance(element, Field):
            if not element.is_valid:
                errors[element.name] = element.errors
        elif isinstance(element, Section):
            errors.update(recursive_validate(element.elements))
    return errors


class Form:
    def __init__(self, name: str, elements: List[Field | Section], title: str = None, data: Dict[str, Any] = None):
        self.code = name
        self.title = title
        self.elements = elements

        # todo: process fields
        self._original_data = data
        self.data = data

        self._errors = None

    @property
    def data(self):
        return recursive_get_value(self.elements)

    @data.setter
    def data(self, data: Dict[str, Any]):
        if data is not None:
            recursive_set_data(self.elements, data)
        self._original_data = data
        self._errors = None

    def _validate(self):
        self._errors = recursive_validate(self.elements)

    @property
    def is_valid(self):
        return len(self.errors) == 0

    @property
    def errors(self) -> dict[str : list[ValidationErrorMessage]] | None:
        if self._errors is None:
            self._validate()
        return self._errors

    # todo: data logging gaat over data in bestand, niet om form errors. Kan weg?
    # def error_messages(self, workflow_id: int) -> list[WorkflowDataLog]:
    #     def genererate_error_messages(workflow_id: int) -> Generator[WorkflowDataLog, None, None]:
    #         for error_field in self.errors:
    #             error_messages: ValidationErrorMessage = self.errors[error_field]
    #             for error_message in error_messages:
    #                 yield WorkflowDataLog.objects.create(
    #                     workflow_id=workflow_id,
    #                     level=custom_logging.ERROR,
    #                     obj_type_id=EnumSourceType.INTERFACE,
    #                     fields=["field, error_type, error_msg"],
    #                     data=dict(
    #                         field=error_field,
    #                         error_type=error_message.get("type", ""),
    #                         error_msg=error_message.get("message", ""),
    #                     ),
    #                     msg_code_id=EnumMessageCode.I010_FOUTIEVE_IMPORT_CONFIGURATIE,
    #                 )
    #
    #     return list(genererate_error_messages(workflow_id))

    def __dict__(self):
        out = {"_type": "Form", "code": self.code, "elements": [element.__dict__() for element in self.elements]}

        if self.title is not None:
            out["title"] = self.title

        return out
