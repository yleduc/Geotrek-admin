from django.conf import settings
from django.db.models import F

from geotrek.api.v2 import serializers as api_serializers, \
    filters as api_filters, viewsets as api_viewsets
from geotrek.api.v2.functions import Transform
from geotrek.api.v2.utils import filter_queryset_related_objects_published
from geotrek.tourism import models as tourism_models


class TouristicContentCategoryViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.GeotrekRelatedPortalTourismFilter,)
    serializer_class = api_serializers.TouristicContentCategorySerializer

    def get_queryset(self):
        qs = tourism_models.TouristicContentCategory.objects \
            .prefetch_related('types') \
            .order_by('pk')  # Required for reliable pagination
        return filter_queryset_related_objects_published(qs, self.request, 'contents')


class TouristicContentViewSet(api_viewsets.GeotrekGeometricViewset):
    filter_backends = api_viewsets.GeotrekGeometricViewset.filter_backends + (api_filters.GeotrekTouristicContentFilter,)
    serializer_class = api_serializers.TouristicContentSerializer
    queryset = tourism_models.TouristicContent.objects.existing()\
        .select_related('category', 'reservation_system') \
        .prefetch_related('source', 'themes', 'type1', 'type2') \
        .annotate(geom_transformed=Transform(F('geom'), settings.API_SRID)) \
        .order_by('pk')  # Required for reliable pagination


class InformationDeskViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.GeotrekRelatedPortalTrekFilter,)
    serializer_class = api_serializers.InformationDeskSerializer

    def get_queryset(self):
        qs = tourism_models.InformationDesk.objects.all()
        return filter_queryset_related_objects_published(qs, self.request, 'treks')
