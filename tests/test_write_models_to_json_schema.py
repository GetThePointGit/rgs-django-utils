"""``write_models_to_json_schema --check``: is een bewaarde kopie van het schema nog bij?

Afnemers (waterworks-ui) houden een gecommitte kopie van het gegenereerde
schema bij. ``--check`` vergelijkt die kopie met een verse generatie en faalt
met een korte samenvatting als ze afwijkt (utils#63, waterworks#494). Geen
database nodig: de generatie loopt alleen over de modelregistratie.
"""

import json
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from rgs_django_utils.commands.export_datamodel_to_json_schema import (
    render_datamodel_json_schema,
    summarize_schema_differences,
)


def _check(pad: str) -> tuple[str, str]:
    """Draai ``--check`` op *pad*; geef (stdout, stderr), of laat CommandError door."""
    uit, fout = StringIO(), StringIO()
    call_command("write_models_to_json_schema", path=pad, check=True, stdout=uit, stderr=fout)
    return uit.getvalue(), fout.getvalue()


class TestWriteModelsToJsonSchemaCheck(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pad = os.path.join(self.tmp.name, "datamodels.schema.json")
        call_command("write_models_to_json_schema", path=self.pad, stdout=StringIO())

    def _schrijf(self, document: dict, **dumps_kwargs) -> None:
        with open(self.pad, "w", encoding="utf-8") as f:
            f.write(json.dumps(document, indent=2, ensure_ascii=False, **dumps_kwargs))

    def _lees(self) -> dict:
        with open(self.pad, encoding="utf-8") as f:
            return json.load(f)

    def test_geschreven_bestand_is_bij(self):
        uit, fout = _check(self.pad)
        self.assertIn("is bij", uit)
        self.assertEqual(fout, "")

    def test_geschreven_bestand_is_byte_identiek_aan_render(self):
        with open(self.pad, encoding="utf-8") as f:
            self.assertEqual(f.read(), render_datamodel_json_schema())

    def test_ontbrekend_bestand_faalt(self):
        os.remove(self.pad)
        with self.assertRaisesMessage(CommandError, "loopt achter"):
            _check(self.pad)

    def test_vervallen_tabel_en_gewijzigd_veld_staan_in_de_samenvatting(self):
        document = self._lees()
        defs = document["$defs"]
        tabellen = [naam for naam, d in defs.items() if isinstance(d.get("properties"), dict) and d["properties"]]
        self.assertGreaterEqual(len(tabellen), 2, "testapp moet minstens twee tabellen met velden exporteren")
        weg, anders = tabellen[0], tabellen[1]
        del defs[weg]
        document["oneOf"] = [r for r in document["oneOf"] if r.get("$ref") != f"#/$defs/{weg}"]
        veld = next(iter(defs[anders]["properties"]))
        defs[anders]["properties"][veld] = {**defs[anders]["properties"][veld], "title": "Handmatig bewerkt"}
        defs[anders]["properties"]["extra_veld_in_kopie"] = {"type": "string"}
        self._schrijf(document)

        fout = StringIO()
        with self.assertRaises(CommandError):
            call_command("write_models_to_json_schema", path=self.pad, check=True, stdout=StringIO(), stderr=fout)
        samenvatting = fout.getvalue()
        self.assertIn(f"nieuwe tabellen (1): {weg}", samenvatting)
        self.assertIn(f"{anders}: velden weg: extra_veld_in_kopie; velden gewijzigd: {veld}", samenvatting)

    def test_alleen_opmaak_verschilt(self):
        self._schrijf(self._lees(), sort_keys=True)
        fout = StringIO()
        with self.assertRaises(CommandError):
            call_command("write_models_to_json_schema", path=self.pad, check=True, stdout=StringIO(), stderr=fout)
        self.assertIn("alleen opmaak of volgorde", fout.getvalue())

    def test_ongeldige_json(self):
        with open(self.pad, "w", encoding="utf-8") as f:
            f.write("{ niet json")
        fout = StringIO()
        with self.assertRaises(CommandError):
            call_command("write_models_to_json_schema", path=self.pad, check=True, stdout=StringIO(), stderr=fout)
        self.assertIn("geen geldige JSON", fout.getvalue())


class TestSummarizeSchemaDifferences(SimpleTestCase):
    """Pure samenvatting, los van de generatie."""

    def _doc(self, defs: dict, **top) -> dict:
        return {"title": "t", "oneOf": [{"$ref": f"#/$defs/{k}"} for k in defs], "$defs": defs, **top}

    def test_gelijk_geeft_niets(self):
        doc = self._doc({"a": {"properties": {"x": {"type": "string"}}}})
        self.assertEqual(summarize_schema_differences(doc, json.loads(json.dumps(doc))), [])

    def test_tabellen_erbij_en_weg(self):
        oud = self._doc({"a": {"properties": {}}, "b": {"properties": {}}})
        nieuw = self._doc({"a": {"properties": {}}, "c": {"properties": {}}})
        self.assertEqual(
            summarize_schema_differences(oud, nieuw),
            ["nieuwe tabellen (1): c", "vervallen tabellen (1): b"],
        )

    def test_velden_en_tabelmetadata(self):
        oud = self._doc({"a": {"title": "A", "required": [], "properties": {"x": {"type": "string"}, "y": {"type": "integer"}}}})
        nieuw = self._doc(
            {"a": {"title": "A2", "required": ["x"], "properties": {"x": {"type": "number"}, "z": {"type": "integer"}}}}
        )
        self.assertEqual(
            summarize_schema_differences(oud, nieuw),
            ["a: velden erbij: z; velden weg: y; velden gewijzigd: x; tabelmetadata gewijzigd: required, title"],
        )

    def test_documentniveau_en_afkappen(self):
        velden = {f"v{i:02d}": {"type": "string"} for i in range(12)}
        oud = self._doc({"a": {"properties": {}}}, description="oud")
        nieuw = self._doc({"a": {"properties": velden}}, description="nieuw")
        regels = summarize_schema_differences(oud, nieuw)
        self.assertEqual(regels[0], "a: velden erbij: v00, v01, v02, v03, v04, v05, v06, v07, … (+4)")
        self.assertEqual(regels[1], "documentniveau gewijzigd: description")
