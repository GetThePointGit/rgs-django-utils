from rgs_utils.database import dj_extended_models as models
from rgs_utils.database.base_models.enums import BaseEnumExtended

from ._enum_sections import section_enum_task


class PoidDataNr:
    PROJECT = 0
    WATERWAY = 1
    WATERWAY_LEGGER = 2
    WATERWAY_ASSESSMENT = 3
    PROFILE_LOCATION = 4
    PROFILE_LEGGER = 5
    PROFILE_MEASUREMENT = 6
    PROFILE_MEASUREMENT_BORING = 7
    LEGGER_TYPE = 8
    POINT_MEASUREMENT = 10
    PROFILE_POINT = 12
    SAMPLE_SECTION = 20
    BORING = 21
    CONTAINER = 22
    # Waterway
    DREDGING_CLUSTER = 30
    DREDGING_METHOD = 31
    SLUDGE_PROCESSING = 32
    PLANNING_VARIANT = 33
    # Other
    OBJECT = 40
    NOTE = 41
    PHOTO = 50
    REMARK = 52

    # meta
    SOURCE = 100


class EnumDataType(BaseEnumExtended):
    PROJECT = "project"
    WATERWAY = "ww"
    WATERWAY_LEGGER = "wleg"
    WATERWAY_ASSESSMENT = "wass"
    PROFILE_LOCATION = "pl"
    PROFILE_LEGGER = "pleg"
    PROFILE_MEASUREMENT = "pm"
    PROFILE_POINT = "pp"
    PROFILE_MEASUREMENT_BORING = "pmboring"
    POINT_MEASUREMENT = "pmeas"
    SAMPLE_SECTION = "ss"
    BORING = "boring"
    CONTAINER = "container"
    # planning
    DREDGING_CLUSTER = "dc"
    DREDGING_METHOD = "dm"
    SLUDGE_PROCESSING = "sp"

    # Other
    OBJECT = "go"
    NOTE = "note"
    PHOTO = "photo"
    REMARK = "remark"

    # meta
    SOURCE = "source"

    order = models.IntegerField(
        verbose_name="volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    poid_nr = models.IntegerField(
        verbose_name="POID nummer",
        default=0,
        config=models.Config(
            doc_short="POID nummer",
            permissions=models.FPerm("-s-", user_self="-s-"),
        ),
    )

    class Meta:
        db_table = "enum_data_type"
        verbose_name = "Datatype"
        verbose_name_plural = "Datatypes"

    class TableDescription:
        section = section_enum_task
        description = "De verschillende datatypes voor exports en imports en configuratie, zoals de id voor in de poid"
        modules = "*"

    @classmethod
    def default_records(cls):
        # todo: get these defaults from the implementations (like core)
        return {
            "fields": ["id", "name", "order", "poid_nr"],
            "data": [
                (cls.PROJECT, "project", PoidDataNr.PROJECT, 0),
                (cls.WATERWAY, "Watergang", PoidDataNr.WATERWAY, 1),
                (cls.WATERWAY_LEGGER, "Watergang legger", PoidDataNr.WATERWAY_LEGGER, 2),
                (cls.WATERWAY_ASSESSMENT, "Watergang toetsing", PoidDataNr.WATERWAY_ASSESSMENT, 3),
                (cls.PROFILE_LOCATION, "profiellocatie", PoidDataNr.PROFILE_LOCATION, 4),
                (cls.PROFILE_LEGGER, "profiellegger", PoidDataNr.PROFILE_LEGGER, 5),
                (cls.PROFILE_MEASUREMENT, "profielmeting", PoidDataNr.PROFILE_MEASUREMENT, 6),
                (cls.PROFILE_MEASUREMENT_BORING, "controleboring", PoidDataNr.PROFILE_MEASUREMENT_BORING, 7),
                (cls.POINT_MEASUREMENT, "puntmeting", PoidDataNr.POINT_MEASUREMENT, 10),
                (cls.PROFILE_POINT, "profielpunt", PoidDataNr.PROFILE_POINT, 12),
                (cls.SAMPLE_SECTION, "monstervak", PoidDataNr.SAMPLE_SECTION, 20),
                (cls.BORING, "boring", PoidDataNr.BORING, 21),
                (cls.CONTAINER, "container", PoidDataNr.CONTAINER, 22),
                # planning
                (cls.DREDGING_CLUSTER, "bagger_cluster", PoidDataNr.DREDGING_CLUSTER, 30),
                (cls.DREDGING_METHOD, "baggermethode", PoidDataNr.DREDGING_METHOD, 31),
                (cls.SLUDGE_PROCESSING, "slibverwerking", PoidDataNr.SLUDGE_PROCESSING, 32),
                # other
                (cls.OBJECT, "object", PoidDataNr.OBJECT, 40),
                (cls.NOTE, "notitie", PoidDataNr.NOTE, 41),
                (cls.PHOTO, "foto", PoidDataNr.PHOTO, 50),
                (cls.REMARK, "opmerking", PoidDataNr.REMARK, 52),
                # meta
                (cls.SOURCE, "bron", PoidDataNr.SOURCE, 100),
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
