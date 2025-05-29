from django.apps import apps
from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnum
from rgs_django_utils.models import EnumImportMode

section_db_description = models.TableSection(
    "model_descr", "modelbeschrijving", 900, "Beschrijving van de database tabellen en velden"
)


__all__ = [
    "DescriptionTableSection",
    "DescriptionEnumTableType",
    "DescriptionTable",
    "DescriptionCalculation",
    "DescriptionFieldSection",
    "DescriptionField",
    "DescriptionFieldInputForCalc",
]


class DescriptionTableSection(models.Model):
    code = models.CharField(
        primary_key=True,
        max_length=50,
        config=models.Config(doc_short="Code van de sectie.", permissions=models.FPerm("-s-", user_self="-s-")),
    )

    name = models.TextField(
        "naam",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Naam van de sectie (in het Nederlands). Wordt gebruikt om de secties te groeperen en sorteren.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    order = models.IntegerField(
        "volgorde",
        db_default=-1,
        config=models.Config(doc_short="Volgorde van de sectie.", permissions=models.FPerm("-s-", user_self="-s-")),
    )

    description = models.TextField(
        "omschrijving",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Omschrijving van de sectie (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "descr_table_section"
        verbose_name = "sectie"
        verbose_name_plural = "secties"

    class TableDescription:
        section = section_db_description
        order = 0
        description = "Secties om de tabellen te groeperen en sorteren"

    def __str__(self):
        return f"{self.name} - ({self.code})"

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )


class DescriptionEnumTableType(BaseEnum):
    ENUM = "enum"
    EXTENDED_ENUM = "extended_enum"
    TABLE = "table"

    class Meta:
        db_table = "descr_enum_table_type"
        verbose_name = "tabeltype"
        verbose_name_plural = "tabeltypes"

    class TableDescription:
        section = section_db_description
        order = 2
        description = "Beschrijving van speciale tabeltypes"

    @classmethod
    def default_records(cls):
        return dict(
            fields=["id", "name"],
            data=[
                dict(id=cls.ENUM, name="enum"),
                dict(id=cls.EXTENDED_ENUM, name="extended enum"),
                dict(id=cls.TABLE, name="tabel"),
            ],
        )

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )


class DescriptionTable(models.Model):
    """Table for descriptions of tables."""

    # primary key
    id = models.CharField(
        "database tabel",
        primary_key=True,
        max_length=100,
        config=models.Config(
            doc_short="Naam van de tabel in de database.", permissions=models.FPerm("-s-", user_self="-s-")
        ),
    )

    section = models.ForeignKey(
        DescriptionTableSection,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="sectie",
        related_name="tables",
        config=models.Config(
            doc_short="Naam van de sectie waar de tabel bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    order = models.IntegerField(
        db_default=-1,
        config=models.Config(doc_short="Volgorde van de tabel.", permissions=models.FPerm("-s-", user_self="-s-")),
    )

    model = models.TextField(
        "model",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Naam van het model in Django (bron code).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    name = models.TextField(
        "naam",
        config=models.Config(
            doc_short="Naam van de tabel (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    name_plural = models.TextField(
        "naam meervoud",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Naam van de tabel in het meervoud (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    description = models.TextField(
        "description",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Beschrijving van de tabel (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    table_type = models.ForeignKey(
        DescriptionEnumTableType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="tabeltype",
        related_name="+",
        config=models.Config(
            doc_short="Type van de tabel.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    modules = models.TextField(
        default="*",
        config=models.Config(
            doc_short="Modules waarin de tabel gebruikt wordt.", permissions=models.FPerm("-s-", user_self="-s-")
        ),
    )

    with_history = models.BooleanField(
        "met historie",
        db_default=False,
        config=models.Config(
            doc_short="Heeft de tabel een historie trigger",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "descr_table"
        verbose_name = "tabelbeschrijving"
        verbose_name_plural = "tabelbeschrijvingen"

    class TableDescription:
        section = section_db_description
        order = 1
        description = "Beschrijving van de databasetabellen"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.name} - ({self.id})"

    def get_real_table(self):
        for model in apps.get_models():
            if model._meta.db_table == self.id:
                return model

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )


class DescriptionCalculation(models.Model):
    """Table for descriptions of calculations."""

    id = models.IntegerField(
        primary_key=True,
        config=models.Config(
            doc_short="Unique identifier for the calculation, as specific numberingsystem is used",
            doc_development="Unique identifier for the calculation in the database.",
            doc_constraint="Unique within the database.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    table = models.ForeignKey(
        DescriptionTable,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="tabel",
        related_name="calculations",
        config=models.Config(
            doc_development="Name of the table in the database.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    name = models.TextField(
        config=models.Config(
            doc_development="Name of the calculation in the database.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    description = models.TextField(
        "description",
        config=models.Config(
            doc_short="Description of the calculation.",
            doc_constraint="Must be unique within the database.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "descr_calculation"
        verbose_name = "berekening"
        verbose_name_plural = "berekeningen"

    class TableDescription:
        section = section_db_description
        order = 3
        description = "Beschrijving van de database berekeningen in de applicatie"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.table} - {self.name}"

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )


class DescriptionFieldSection(models.Model):
    table = models.ForeignKey(
        DescriptionTable,
        on_delete=models.CASCADE,
        related_name="field_sections",
        verbose_name="tabel",
        config=models.Config(
            doc_short="Naam van de tabel waar de sectie bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    code = models.CharField(
        max_length=50,
        config=models.Config(
            doc_short="Naam van de tabel waar de sectie bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    name = models.TextField(
        "naam",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Naam van de tabel waar de sectie bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    order = models.IntegerField(
        "volgorde",
        db_default=-1,
        config=models.Config(
            doc_short="Naam van de tabel waar de sectie bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    description = models.TextField(
        "omschrijving",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Naam van de tabel waar de sectie bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "descr_field_section"
        verbose_name = "veldsectie"
        verbose_name_plural = "veldsecties"

        constraints = [models.UniqueConstraint(fields=["table", "code"], name="unique_section")]

    class TableDescription:
        section = section_db_description
        order = 4
        description = "Secties om de databasevelden in een tabel te groeperen en sorteren"

    def __str__(self):
        return self.name

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )


class DescriptionField(models.Model):
    """Table for descriptions of fields."""

    table = models.ForeignKey(
        DescriptionTable,
        on_delete=models.CASCADE,
        verbose_name="tabel",
        related_name="fields",
        config=models.Config(
            doc_short="Naam van de tabel waar het veld bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    field_section = models.ForeignKey(
        DescriptionFieldSection,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fields",
        verbose_name="veldsectie",
        config=models.Config(
            doc_short="Naam van de sectie waar het veld bij hoort.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    order = models.IntegerField(
        "volgorde",
        db_default=-1,
        config=models.Config(
            doc_short="volgorde van de kolom in de tabel. gebruikt voor beschrijving",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    column_name = models.TextField(
        "kolomnaam",
        config=models.Config(
            doc_short="Naam van de kolom in de database.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    verbose_name = models.TextField(
        "naam",
        config=models.Config(
            doc_short="Naam van het veld (in het Nederlands).", permissions=models.FPerm("-s-", user_self="-s-")
        ),
    )
    dbf_name = models.CharField(
        "dbf naam",
        max_length=10,
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Naam van de kolom in de dbf file.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    field_type = models.TextField(
        "veldtype",
        config=models.Config(
            doc_short="Type van het veld in de database.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    max_length = models.IntegerField(
        "maximale lengte",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Maximale lengte van het veld in de database.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    nullable = models.BooleanField(
        "nullable",
        config=models.Config(
            doc_short="Geeft aan of het veld in de database NULL waardes kan bevatten.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    precision = models.IntegerField(
        "aantal decimalen",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="aantal decimalen voor exports, etc.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    is_relation = models.BooleanField(
        "is relatie",
        db_default=False,
        config=models.Config(
            doc_short="Geeft aan of het veld een relatie heeft met een andere tabel.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    relation_table = models.ForeignKey(
        DescriptionTable,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="relation_fields",
        verbose_name="relatie tabel",
        config=models.Config(
            doc_short="Naam van de tabel waarmee het veld een relatie heeft.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    modules = models.TextField(
        default="*",
        config=models.Config(
            doc_short="Modules waarin het veld gebruikt wordt.", permissions=models.FPerm("-s-", user_self="-s-")
        ),
    )

    doc_unit = models.TextField(
        "eenheid",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Eenheid van het veld.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    doc_short = models.TextField(
        "omschrijving kort",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Korte omschrijving van het veld (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    doc_full = models.TextField(
        "omschrijving volledig",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Volledige omschrijving van het veld (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    doc_constraint = models.TextField(
        "omschrijving voorwaarde",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Omschrijving van de voorwaarde van het veld (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    doc_development = models.TextField(
        "omschrijving voor ontwikkelaars",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Omschrijving van het veld voor ontwikkelaars (in het Nederlands).",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    import_mode = models.ForeignKey(
        EnumImportMode,
        on_delete=models.PROTECT,
        default=EnumImportMode.ALL,
        verbose_name="import mode",
        related_name="+",
        config=models.Config(
            doc_short="Import modus van het veld.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    export = models.BooleanField(
        "export",
        db_default=True,
        config=models.Config(
            doc_short="Geeft aan of het veld geëxporteerd moet worden.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    calc_by = models.ForeignKey(
        DescriptionCalculation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="berekening",
        related_name="fields",
        config=models.Config(
            doc_short="Berekening van het veld.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    default_value = models.TextField(
        "default waarde of functie",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Default waarde of functie van het veld.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    with_history = models.BooleanField(
        "gebruikt in historie trigger",
        db_default=False,
        config=models.Config(
            doc_short="Geeft aan of het veld gebruikt wordt in de historie trigger.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "descr_field"
        verbose_name = "veld"
        verbose_name_plural = "velden"

        constraints = [models.UniqueConstraint(fields=["table", "column_name"], name="unique_descr_field")]

    class TableDescription:
        section = section_db_description
        order = 5
        description = "Beschrijving van de databasevelden"

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )


class DescriptionFieldInputForCalc(models.Model):
    calc = models.ForeignKey(
        DescriptionCalculation,
        on_delete=models.CASCADE,
        verbose_name="berekening",
        related_name="input_fields",
        config=models.Config(
            doc_short="Berekening waarvoor het veld als input dient.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    field = models.ForeignKey(
        DescriptionField,
        on_delete=models.CASCADE,
        verbose_name="veld",
        related_name="input_for_calc",
        config=models.Config(
            doc_short="Veld dat als input dient voor de berekening.",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "descr_field_input_for_calc"
        verbose_name = "veld input voor berekening"
        verbose_name_plural = "veld input voor berekeningen"

        constraints = [models.UniqueConstraint(fields=["calc", "field"], name="unique_descr_field_input_for_calc")]

    class TableDescription:
        section = section_db_description
        order = 6
        description = "Beschrijving van de velden die als input dienen voor berekeningen"

    @classmethod
    def permissions(cls):
        no_filt = {}  # authenitcation module must be able to see all users

        return models.TPerm(
            public={
                "select": no_filt,
            },
            user_self={
                "select": no_filt,
            },
        )
