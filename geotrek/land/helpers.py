import logging

from django.contrib.gis.geos import GEOSGeometry
from django.utils import translation
from django.utils.translation import ugettext as _
from django.contrib.gis.geos import LineString
from django.conf import settings
from django.db import connection

import pygal
from pygal.style import CleanStyle


logger = logging.getLogger(__name__)


class LandHelper(object):
    @classmethod
    def land_profile_svg(cls, language):
        """
        Plot the altimetric graph in SVG using PyGal.
        Most of the job done here is dedicated to preparing
        nice labels scales.
        """
        print("coco")
        config = dict(show_legend=True,
                      value_formatter=lambda v: '%d' % v,
                      margin=settings.LAND_PROFILE_FONTSIZE,
                      width=settings.LAND_PROFILE_WIDTH,
                      height=settings.LAND_PROFILE_HEIGHT,
                      title_font_size=settings.LAND_PROFILE_FONTSIZE,
                      label_font_size=0.8 * settings.LAND_PROFILE_FONTSIZE,
                      major_label_font_size=settings.LAND_PROFILE_FONTSIZE,
                      js=[])

        style = CleanStyle
        style.background = settings.LAND_PROFILE_BACKGROUND
        style.colors = (settings.LAND_PROFILE_COLOR,)
        style.font_family = settings.LAND_PROFILE_FONT
        line_chart = pygal.Bar(fill=True, style=style, **config)
        if language:
            translation.activate(language)
        line_chart.x_title = _("Types")
        line_chart.y_title = _("Number")
        line_chart.show_minor_x_labels = False
        line_chart.x_labels_major_count = 5
        line_chart.show_minor_y_labels = False
        line_chart.truncate_label = 50
        line_chart.no_data_text = _(u"No Land Status")
        translation.deactivate()
        line_chart.add('', [(int(v[0]), int(v[3])) for v in profile])
        return line_chart.render()
