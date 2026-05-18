from abc import ABC, abstractmethod
from typing import Self, Type

all = []


class HasuraTrackedView(ABC):
    def __init__(self, db_view):
        self._meta = self.Meta(db_view)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        all.append(cls)

    def __repr__(self):
        return self.get_sql()

    def __name__(self):
        return "_".join(part.capitalize() for part in self._meta.db_table.split("_"))

    @property
    def db_table_name(self):
        return self._meta.db_table

    @property
    def db_view_name(self):
        return f"vw_{self._meta.db_table}"

    @staticmethod
    def all() -> list[Type[Self]]:
        """All classes that inherit HasuraTrackedView. Used for auto generation of tracked views and permissions in hasura.

        Returns
        -------
            list[Type[Self]]: All classes that inherit HasuraTrackedView.

        Example
        -------
        ```python
        views = HasuraTrackedView.all()
        # returns [<class 'UserView'>, <class 'AnotherView'>, ...]
        ```
        """
        return set(all)

    @classmethod
    @abstractmethod
    def get_permissions(cls):
        """
        Permissions for the view. Used for auto generation of permissions in hasura.

        Example
        -------
        ```python
        view = SomeView()
        view.get_permissions()
        ```
        """
        ...

    @abstractmethod
    def get_relations(self):
        """Get the relations for the view. Used for auto generation of permissions in hasura.

        Example
        -------
        ```python
        view = SomeView()
        view.get_relations()
        ```
        """
        ...

    @classmethod
    @abstractmethod
    def get_all_views(cls) -> list[Self]:
        """
        Return all views of the class. Used for auto generation of views in postgresql.

        Example
        -------
        ```python
        all_views = HasuraTrackedView.get_all_views()
        # returns [HasuraTrackedView("vw_ww_user"), HasuraTrackedView("vw_pl_user"), ...]
        ```
        """
        ...

    @abstractmethod
    def get_sql(self) -> str:
        """
        Return the sql for the view. Used for auto generation of views in postgresql.

        Example
        -------
        ```python
        view = UserView("vw_ww_user")
        view.get_sql()
        # returns "DROP VIEW IF EXISTS "vw_ww_user"; CREATE OR REPLACE VIEW vw_ww_user AS SELECT ... FROM ..."
        ```
        """
        ...

    class Meta:
        def __init__(self, db_view):
            self.db_table = db_view

        view = True
        abstract = True


class ViewField(object):
    def __init__(self, name, verbose_name, column, config):
        self.name = name
        self.verbose_name = verbose_name
        self.column = column
        self.r_config = config
        self.is_relation = False
        self.primary_key = False
