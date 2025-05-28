from typing import Generic, List, TypeVar

from rgs_utils.forms.fields.Field import Field

SectionType = TypeVar("SectionType")


class Section(Generic[SectionType]):
    def __init__(
        self, elements: List[Field | SectionType], title: str = None, description: str = None, collapsed: bool = False
    ):
        self.title = title
        self.description = description
        self.elements = elements
        self.collapsed = collapsed

    def is_valid(self):
        return True

    def get_errors(self):
        return {}

    def __dict__(self):
        out = {
            "_type": "Section",
            "collapsed": self.collapsed,
            "elements": [element.__dict__() for element in self.elements],
        }

        if self.title is not None:
            out["title"] = self.title

        if self.description is not None:
            out["description"] = self.description

        return out
