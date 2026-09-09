from django.test import SimpleTestCase

from ingestion.text_normalizer import repair_mojibake


class MojibakeRepairTests(SimpleTestCase):
    ### Verify that common UTF-8 mojibake is repaired correctly.
    def test_repairs_common_spanish_accents(self):
        self.assertEqual(
            repair_mojibake("RegiÃ³n de TarapacÃ¡"),
            "Región de Tarapacá",
        )

    ### Verify that multiple accented characters are repaired in one value.
    def test_repairs_multiple_accents(self):
        self.assertEqual(
            repair_mojibake(
                "RegiÃ³n de AysÃ©n del Gral.IbaÃ±ez del Campo"
            ),
            "Región de Aysén del Gral.Ibañez del Campo",
        )

    ### Verify that the actual mojibake representation produced by GDAL
    ### for the Ñ character is repaired correctly.
    def test_repairs_enye(self):
        self.assertEqual(
            repair_mojibake("RegiÃ³n de Ã\x91uble"),
            "Región de Ñuble",
        )

    ### Verify that mojibake containing í is repaired correctly.
    def test_repairs_i_accent(self):
        self.assertEqual(
            repair_mojibake("RegiÃ³n de ValparaÃ\xadso"),
            "Región de Valparaíso",
        )

    ### Verify that text without encoding corruption is preserved.
    def test_preserves_valid_unicode(self):
        value = "Región Metropolitana de Santiago"

        self.assertEqual(
            repair_mojibake(value),
            value,
        )

    ### Verify that plain ASCII text is preserved.
    def test_preserves_ascii(self):
        value = "Maule"

        self.assertEqual(
            repair_mojibake(value),
            value,
        )

    ### Verify that empty values are preserved.
    def test_preserves_empty_value(self):
        self.assertEqual(
            repair_mojibake(""),
            "",
        )

    ### Verify that NULL-like Python values are preserved.
    def test_preserves_none(self):
        self.assertIsNone(
            repair_mojibake(None)
        )