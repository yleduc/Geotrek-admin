from django.conf import settings
from django.conf.urls import url

from mapentity.registry import registry

from . import models
from views import LandChart

urlpatterns = registry.register(models.PhysicalEdge, menu=False)
urlpatterns += registry.register(models.LandEdge, menu=settings.TREKKING_TOPOLOGY_ENABLED and settings.LANDEDGE_MODEL_ENABLED)
urlpatterns += registry.register(models.CompetenceEdge, menu=False)
urlpatterns += registry.register(models.WorkManagementEdge, menu=False)
urlpatterns += registry.register(models.SignageManagementEdge, menu=False)

urlpatterns += [url(r'^api/(?P<lang>\w+)/land/physicaledges/profile.svg$', LandChart.as_view(model=models.PhysicalEdge),
                    name='land_profile_svg'),
]
