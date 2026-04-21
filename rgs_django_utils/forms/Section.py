from typing import Generic, List, TypeVar

from rgs_django_utils.forms.fields.Field import Field

SectionType = TypeVar("SectionType")


class Section(Generic[SectionType]):
    """Visual grouping of :class:`Field` (and nested :class:`Section`) elements.

    A section contributes no validation on its own — it just carries
    display metadata (title, description, collapsed-by-default) and hands
    responsibility down to its children.

    Parameters
    ----------
    elements : list of Field or Section
        Children to render inside the section.
    title : str, optional
        Heading shown above the section.
    description : str, optional
        Short explanation shown below the title.
    collapsed : bool, optional
        If ``True`` the UI renders the section collapsed by default.
        Default is ``False``.
    """

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
