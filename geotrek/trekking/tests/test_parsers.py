import os

from django.contrib.gis.geos import Point, LineString, MultiLineString, WKTWriter
from django.core.management import call_command
from django.test import TestCase

from geotrek.common.models import Theme, FileType
from geotrek.trekking.models import Trek, DifficultyLevel, Route
from geotrek.trekking.parsers import TrekParser


class TrekParserFilterDurationTests(TestCase):
    def setUp(self):
        self.parser = TrekParser()

    def test_standard(self):
        self.assertEqual(self.parser.filter_duration('duration', '0 h 30'), 0.5)
        self.assertFalse(self.parser.warnings)

    def test_upper_h(self):
        self.assertEqual(self.parser.filter_duration('duration', '1 H 06'), 1.1)
        self.assertFalse(self.parser.warnings)

    def test_spaceless(self):
        self.assertEqual(self.parser.filter_duration('duration', '2h45'), 2.75)
        self.assertFalse(self.parser.warnings)

    def test_no_minutes(self):
        self.assertEqual(self.parser.filter_duration('duration', '3 h'), 3.)
        self.assertFalse(self.parser.warnings)

    def test_no_hours(self):
        self.assertEqual(self.parser.filter_duration('duration', 'h 12'), None)
        self.assertTrue(self.parser.warnings)

    def test_spacefull(self):
        self.assertEqual(self.parser.filter_duration('duration', '\n \t  4     h\t9\r\n'), 4.15)
        self.assertFalse(self.parser.warnings)

    def test_float(self):
        self.assertEqual(self.parser.filter_duration('duration', '5.678'), 5.678)
        self.assertFalse(self.parser.warnings)

    def test_coma(self):
        self.assertEqual(self.parser.filter_duration('duration', '6,7'), 6.7)
        self.assertFalse(self.parser.warnings)

    def test_integer(self):
        self.assertEqual(self.parser.filter_duration('duration', '7'), 7.)
        self.assertFalse(self.parser.warnings)

    def test_negative_number(self):
        self.assertEqual(self.parser.filter_duration('duration', '-8'), None)
        self.assertTrue(self.parser.warnings)

    def test_negative_hours(self):
        self.assertEqual(self.parser.filter_duration('duration', '-8 h 00'), None)
        self.assertTrue(self.parser.warnings)

    def test_negative_minutes(self):
        self.assertEqual(self.parser.filter_duration('duration', '8 h -15'), None)
        self.assertTrue(self.parser.warnings)

    def test_min_gte_60(self):
        self.assertEqual(self.parser.filter_duration('duration', '9 h 60'), None)
        self.assertTrue(self.parser.warnings)


class TrekParserFilterGeomTests(TestCase):
    def setUp(self):
        self.parser = TrekParser()

    def test_empty_geom(self):
        self.assertEqual(self.parser.filter_geom('geom', None), None)
        self.assertFalse(self.parser.warnings)

    def test_point(self):
        geom = Point(0, 0)
        self.assertEqual(self.parser.filter_geom('geom', geom), None)
        self.assertTrue(self.parser.warnings)

    def test_linestring(self):
        geom = LineString((0, 0), (0, 1), (1, 1), (1, 0))
        self.assertEqual(self.parser.filter_geom('geom', geom), geom)
        self.assertFalse(self.parser.warnings)

    def test_multilinestring(self):
        geom = MultiLineString(LineString((0, 0), (0, 1), (1, 1), (1, 0)))
        self.assertEqual(self.parser.filter_geom('geom', geom),
                         LineString((0, 0), (0, 1), (1, 1), (1, 0)))
        self.assertFalse(self.parser.warnings)

    def test_multilinestring_with_hole(self):
        geom = MultiLineString(LineString((0, 0), (0, 1)), LineString((100, 100), (100, 101)))
        self.assertEqual(self.parser.filter_geom('geom', geom),
                         LineString((0, 0), (0, 1), (100, 100), (100, 101)))
        self.assertTrue(self.parser.warnings)


WKT = (
    b'LINESTRING (356392.8993 6689612.1026, 356466.0588 6689740.1317, 356411.1892 6689868.1609, '
    b'356566.6531 6689904.7406, 356712.9721 6689804.1463, 356703.8271 6689703.5520, 356621.5227 6689639.5374, '
    b'356612.3778 6689511.5083, 356447.7689 6689502.3634)'
)


class TrekParserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.difficulty = DifficultyLevel.objects.create(difficulty="Facile")
        cls.route = Route.objects.create(route="Boucle")
        cls.themes = (
            Theme.objects.create(label="Littoral"),
            Theme.objects.create(label="Marais"),
        )
        cls.filetype = FileType.objects.create(type="Photographie")

    def test_create(self):
        filename = os.path.join(os.path.dirname(__file__), 'data', 'trek.shp')
        call_command('import', 'geotrek.trekking.parsers.TrekParser', filename, verbosity=0)
        trek = Trek.objects.all().last()
        self.assertEqual(trek.name, "Balade")
        self.assertEqual(trek.difficulty, self.difficulty)
        self.assertEqual(trek.route, self.route)
        self.assertQuerysetEqual(trek.themes.all(), [repr(t) for t in self.themes], ordered=False)
        self.assertEqual(WKTWriter(precision=4).write(trek.geom), WKT)
