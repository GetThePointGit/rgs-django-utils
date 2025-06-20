import logging
import os

import xlsxwriter

log = logging.getLogger(__name__)


if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django(log)

from thissite import settings

from rgs_django_utils.models import DescriptionField, DescriptionTable, DescriptionTableSection

table_fields = {
    "naam": "name",
    "naam meervoud": "name_plural",
    "volgorde": "order",
    "django model": "model",
    "database model": "id",
    "tabeltype": "table_type_id",
    "modules": "modules",
    "met historie": "with_history",
}

field_fields = {
    "naam": "verbose_name",
    "kolomnaam": "column_name",
    "dbf naam": "dbf_name",
    "sectie": "field_section__name",
    "volgorde": "order",
    "veldtype": "field_type",
    "maximale lengte": "max_length",
    "nullable": "nullable",
    "aantal decimalen": "precision",
    # "is relatie": "is_relation",
    "relatie tabel": "relation_table_id",
    # "import": "import_mode",
    "export": "export",
    "modules": "modules",
    "eenheid": "doc_unit",
    "omschrijving kort": "doc_short",
    "omschrijving volledig": "doc_full",
    "omschrijving voorwaarde": "doc_constraint",
    "omschrijving voor ontwikkelaars": "doc_development",
    "berekening": "calc_by_id",
    "default waarde of functie": "default_value",
    # "gebruikt in historie trigger": "with_history",
}


class Styles:
    def __init__(self, workbook):
        self.workbook = workbook

        self.h1 = workbook.add_format(
            {
                "bold": True,
                "font_size": 16,
            }
        )

        self.h2 = workbook.add_format(
            {
                "bold": True,
                "font_size": 14,
            }
        )

        self.h3 = workbook.add_format(
            {
                "bold": True,
                "font_size": 12,
            }
        )

        self.h_description = workbook.add_format(
            {
                "italic": True,
                "font_size": 10,
            }
        )

        self.table_header = workbook.add_format(
            {
                "bold": True,
                "font_size": 10,
                "bg_color": "#F0F0F0",
                "top": 1,
                "bottom": 1,
            }
        )

        table_odd = {
            "left": 1,
            "left_color": "#F0F0F0",
        }
        table_even = {
            **table_odd,
            "bg_color": "#F9F9F9",
        }
        table_top = {
            **table_odd,
            "top": 1,
        }

        table_bottom_even = {
            **table_even,
            "bottom": 1,
        }
        table_bottom_odd = {
            **table_odd,
            "bottom": 1,
        }

        self.table_field_odd = workbook.add_format(table_odd)
        self.table_field_even = workbook.add_format(table_even)
        self.table_top_table = workbook.add_format(table_top)
        self.table_bottom_table_even = workbook.add_format(table_bottom_even)
        self.table_bottom_table_odd = workbook.add_format(table_bottom_odd)

        # gray and italic
        default_val_style = {
            "font_color": "#888888",
            "italic": True,
        }
        self.table_field_odd_def = workbook.add_format(
            {
                **table_odd,
                **default_val_style,
            }
        )
        self.table_field_even_def = workbook.add_format(
            {
                **table_even,
                **default_val_style,
            }
        )
        self.table_top_table_def = workbook.add_format(
            {
                **table_top,
                **default_val_style,
            }
        )
        self.table_bottom_table_even_def = workbook.add_format(
            {
                **table_bottom_even,
                **default_val_style,
            }
        )
        self.table_bottom_table_odd_def = workbook.add_format(
            {
                **table_bottom_odd,
                **default_val_style,
            }
        )


def table_field_style(styles, row, rows, use_even_odd=True, for_default=False):
    if row == 0:
        if for_default:
            return styles.table_top_table_def
        return styles.table_top_table
    elif row == rows - 1:
        if row % 2 == 0 and use_even_odd:
            if for_default:
                return styles.table_bottom_table_even_def
            return styles.table_bottom_table_even
        else:
            if for_default:
                return styles.table_bottom_table_odd_def
            return styles.table_bottom_table_odd
    elif row % 2 == 0 and use_even_odd:
        if for_default:
            return styles.table_field_even_def
        return styles.table_field_even
    else:
        if for_default:
            return styles.table_field_odd_def
        return styles.table_field_odd


def export_datamodel_to_excel(export_path=None):
    if export_path is None:
        export_path = os.path.join(settings.BASE_DIR, os.pardir, "var", "datamodel.xlsx")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)

    print(f"Exporting datamodel to {export_path}")

    workbook = xlsxwriter.Workbook(export_path)

    styles = Styles(workbook)

    overview = workbook.add_worksheet("Overzicht")
    overview.write(0, 0, "Overzicht", styles.h1)
    overview_row = 2

    for section in DescriptionTableSection.objects.all().order_by("order"):
        row = 0

        ### table section
        worksheet = workbook.add_worksheet(section.name)
        worksheet.write(0, 0, f"Sectie {section.name} ({section.code})", styles.h1)

        overview.write(overview_row, 0, f"Sectie {section.name}", styles.h2)
        overview_row += 1

        if section.description:
            worksheet.write(1, 0, section.description, styles.h_description)
            overview.write(overview_row, 0, section.description, styles.h_description)
            overview_row += 1

        row += 3

        overview.write(overview_row, 0, "naam", styles.table_header)
        overview.write(overview_row, 1, "db table", styles.table_header)
        overview.write(overview_row, 2, "module", styles.table_header)
        overview.write(overview_row, 3, "beschrijving", styles.table_header)
        overview_row += 1

        tables = list(DescriptionTable.objects.filter(section=section).order_by("order"))

        for i, table in enumerate(tables):
            ### table
            style = table_field_style(styles, i, len(tables), use_even_odd=True)
            overview.write(overview_row, 0, table.name, style)
            overview.write(overview_row, 1, table.id, style)
            overview.write(overview_row, 2, table.modules, style)
            overview.write(overview_row, 3, table.description, style)
            overview_row += 1

            worksheet.write(row, 0, f"Tabel {table.name} ({table.id})", styles.h2)
            if table.description:
                row += 1
                worksheet.write(row, 0, table.description, styles.h_description)
            row += 2

            items = table_fields.items()
            for ii, (name, field) in enumerate(items):
                style = table_field_style(styles, ii, len(items), use_even_odd=False)

                worksheet.write(row, 0, name, style)
                worksheet.write(row, 1, getattr(table, field), style)
                row += 1

            row += 1

            ###fields
            # header for field table
            for ii, name in enumerate(field_fields.keys()):
                worksheet.write(row, ii, name, styles.table_header)

            row += 1

            fields = list(
                DescriptionField.objects.filter(table=table).order_by("order").values(*field_fields.values())
            )  #'field_section__order',
            # columns for fields
            for ii, field in enumerate(fields):
                style = table_field_style(styles, ii, len(fields), use_even_odd=True)
                style_def = table_field_style(styles, ii, len(fields), use_even_odd=True, for_default=True)

                for iii, (name, col) in enumerate(field_fields.items()):
                    if col == "dbf_name":
                        if field.get(col):
                            worksheet.write(row, iii, field.get(col), style)
                        else:
                            worksheet.write(row, iii, field.get("column_name")[:10], style_def)
                    else:
                        worksheet.write(row, iii, field.get(col), style)
                row += 1

            row += 1
            real_table = table.get_real_table()

            if hasattr(real_table, "default_records") and len(real_table.default_records().get("data")) > 0:
                worksheet.write(row, 0, "Default records", styles.h3)
                row += 1
                for ii, name in enumerate(real_table.default_records()["fields"]):
                    worksheet.write(row, ii, name, styles.table_header)
                row += 1

                for i, record in enumerate(real_table.default_records()["data"]):
                    style = table_field_style(styles, i, len(real_table.default_records()["data"]), use_even_odd=True)
                    if type(record) == dict:
                        for ii, col in enumerate(real_table.default_records()["fields"]):
                            worksheet.write(row, ii, record[col], style)
                    else:
                        for ii, value in enumerate(record):
                            if type(value) == list:
                                value = str(value)
                            worksheet.write(row, ii, value, style)
                    row += 1

                row += 1
            row += 1

        # worksheet.autofit()
        worksheet.set_column(0, 1, 23)
        worksheet.set_column(2, 12, 15)
        worksheet.set_column(13, 17, 30)
        worksheet.set_column(18, 20, 20)

        overview_row += 1

    overview.set_column(0, 0, 30)
    overview.set_column(1, 1, 30)
    overview.set_column(2, 2, 10)
    overview.set_column(3, 3, 50)

    workbook.close()


if __name__ == "__main__":
    export_datamodel_to_excel(os.path.join(os.path.dirname(__file__), "datamodel2.xlsx"))
