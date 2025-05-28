from rgs_utils.database import dj_extended_models as models
from rgs_utils.database.base_models.enums import BaseEnumExtended
from rgs_utils.models.enums._enum_sections import section_enum_task


class EnumMessageCode(BaseEnumExtended):
    I010_FOUTIEVE_IMPORT_CONFIGURATIE = "I010"
    I240_MISSENDE_GEOMETRIE = "I240"
    I241_FOUTIEVE_GEOMETRIETYPE = "I241"
    I311_DUBBELE_PROFIELEN = "I311"
    I232_FOUTIEF_AANTAL_TT = "I232"
    I233_SOLID_ABOVE_SLUDGE = "I233"
    I234_GEEN_VERSIE = "I234"
    I235_MEERDERE_VERSIES = "I235"
    I236_VERSIE_NIET_ONDERSTEUND = "I236"
    I237_ONBEKEND_TYPE = "I237"
    I238_KON_OBJECTEN_NIET_INLEZEN = "I238"

    template = models.TextField(
        "template",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Template voor de melding",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )
    template_fields = models.ArrayField(
        models.TextField(),
        config=models.Config(
            doc_short="Velden in de template",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_message_code"
        verbose_name = "Meldingscode"
        verbose_name_plural = "Meldingscodes"

    class TableDescription:
        section = section_enum_task
        description = "De verschillende meldingscodes"
        modules = "*"

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name", "template", "template_fields"],
            "data": [
                (
                    cls.I010_FOUTIEVE_IMPORT_CONFIGURATIE,
                    "Import configuratie bevat fouten.",
                    "Veld: {field}, fout: {error_type}, melding: {error_msg}",
                    ["field", "error_type", "error_msg"],
                ),
                (
                    cls.I240_MISSENDE_GEOMETRIE,
                    "Geometrie ontbreekt",
                    "De geometrie van de {object} is niet ingevuld.",
                    ["object"],
                ),
                (
                    cls.I241_FOUTIEVE_GEOMETRIETYPE,
                    "Onjuist geometrie type",
                    "De geometrie van de {object} is van het type {type} en moet van het type {expected_type} zijn.",
                    ["object", "type", "expected_type"],
                ),
                (
                    cls.I311_DUBBELE_PROFIELEN,
                    "Dubbele profiel",
                    "In de import is een profiel twee of meerdere keren gevonden. Profiel: {profile}",
                    ["profile"],
                ),
                (
                    cls.I232_FOUTIEF_AANTAL_TT,
                    "Foutief aantal waterlijnpunten",
                    "Het aantal waterlijnpunten voor profiel {profile} in de import is {count}.",
                    ["profile", "count"],
                ),
                (
                    cls.I233_SOLID_ABOVE_SLUDGE,
                    "Vaste bodem boven slibslaag",
                    "De hoogte voor vaste bodem ({solid_level} mNAP) ligt boven de slibslaag ({sludge_level} mNAP) op punt {point} voor profiel {profile}.",
                    ["profile", "point", "solid_level", "sludge_level"],
                ),
                (
                    cls.I234_GEEN_VERSIE,
                    "Geen versie gevonden",
                    "Er is geen versie gevonden in het bestand.",
                    [],
                ),
                (
                    cls.I235_MEERDERE_VERSIES,
                    "Verschillende versies gevonden",
                    "Er zijn verschillende versies gevonden in het bestand. Versies: {versions}",
                    ["versions"],
                ),
                (
                    cls.I236_VERSIE_NIET_ONDERSTEUND,
                    "Versie niet ondersteund",
                    "De versie van het bestand wordt niet ondersteund. Gevonden versie: {version}. Ondersteunde versies: {supported_versions}",
                    ["version", "supported_versions"],
                ),
                (
                    cls.I237_ONBEKEND_TYPE,
                    "Onbekend type",
                    "Het type {type} is onbekend. De ondersteunde types zijn ({supported_types}).",
                    ["type", "supported_types"],
                ),
                (
                    cls.I238_KON_OBJECTEN_NIET_INLEZEN,
                    "Kon objecten niet inlezen",
                    "{objecten} konden niet worden ingelezen. Controleer het bestand op onjuistheden.",
                    ["objecten"],
                ),
            ],
        }

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
