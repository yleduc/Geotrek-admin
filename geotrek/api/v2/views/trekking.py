from django.conf import settings
from django.db.models import F, Q
from django.db.models.aggregates import Count
from django.http import Http404

from rest_framework.response import Response

from geotrek.api.v2 import serializers as api_serializers, \
    viewsets as api_viewsets, filters as api_filters
from geotrek.api.v2.functions import Transform, Length, Length3D
from geotrek.api.v2.utils import filter_queryset_related_objects_published
from geotrek.trekking import models as trekking_models


class TrekViewSet(api_viewsets.GeotrekGeometricViewset):
    filter_backends = api_viewsets.GeotrekGeometricViewset.filter_backends + (api_filters.GeotrekTrekQueryParamsFilter,)
    serializer_class = api_serializers.TrekSerializer
    queryset = trekking_models.Trek.objects.existing() \
        .select_related('topo_object') \
        .prefetch_related('topo_object__aggregations', 'accessibilities', 'attachments') \
        .annotate(geom3d_transformed=Transform(F('geom_3d'), settings.API_SRID),
                  length_2d_m=Length('geom'),
                  length_3d_m=Length3D('geom_3d')) \
        .order_by('pk')  # Required for reliable pagination

    def retrieve(self, request, pk=None, format=None):
        # Return detail view even for unpublished treks that are childrens of other published treks
        qs_filtered = self.filter_published_lang_retrieve(request, self.queryset)
        trek = qs_filtered.get(pk=pk)
        if not trek:
            raise Http404('No %s matches the given query.' % self.queryset.model._meta.object_name)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(trek, many=False, context={'request': request})
        return Response(serializer.data)

    def filter_published_lang_retrieve(self, request, queryset):
        # filter trek by publication language (including parents publication language)
        qs = queryset
        language = request.GET.get('language', 'all')
        associated_published_fields = [f.name for f in qs.model._meta.get_fields() if f.name.startswith('published')]

        if language == 'all':
            # no language specified. Check for all.
            q = Q()
            for lang in settings.MODELTRANSLATION_LANGUAGES:
                field_name = 'published_{}'.format(lang)
                if field_name in associated_published_fields:
                    field_name_parent = 'trek_parents__parent__published_{}'.format(lang)
                    q |= Q(**{field_name: True}) | Q(**{field_name_parent: True})
            qs = qs.filter(q)
        else:
            # one language is specified
            field_name = 'published_{}'.format(language)
            field_name_parent = 'trek_parents__parent__published_{}'.format(language)
            qs = qs.filter(Q(**{field_name: True}) | Q(**{field_name_parent: True}))
        return qs.distinct()


class TourViewSet(TrekViewSet):
    serializer_class = api_serializers.TourSerializer
    queryset = TrekViewSet.queryset.annotate(count_children=Count('trek_children')) \
        .filter(count_children__gt=0)


class PracticeViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.GeotrekRelatedPortalTrekFilter,)
    serializer_class = api_serializers.PracticeSerializer

    def get_queryset(self):
        qs = trekking_models.Practice.objects.all()
        return filter_queryset_related_objects_published(qs, self.request, 'treks')


class NetworksViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.GeotrekRelatedPortalTrekFilter,)
    serializer_class = api_serializers.NetworkSerializer

    def get_queryset(self):
        qs = trekking_models.TrekNetwork.objects.all()
        return filter_queryset_related_objects_published(qs, self.request, 'treks')


class DifficultyViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.GeotrekRelatedPortalTrekFilter,)
    serializer_class = api_serializers.TrekDifficultySerializer

    def get_queryset(self):
        qs = trekking_models.DifficultyLevel.objects.all()
        return filter_queryset_related_objects_published(qs, self.request, 'treks')


class POIViewSet(api_viewsets.GeotrekGeometricViewset):
    filter_backends = api_viewsets.GeotrekGeometricViewset.filter_backends + (api_filters.GeotrekPOIFilter,)
    serializer_class = api_serializers.POISerializer
    queryset = trekking_models.POI.objects.existing() \
        .select_related('topo_object', 'type', ) \
        .prefetch_related('topo_object__aggregations', 'attachments') \
        .annotate(geom3d_transformed=Transform(F('geom_3d'), settings.API_SRID)) \
        .order_by('pk')  # Required for reliable pagination


class POITypeViewSet(api_viewsets.GeotrekViewSet):
    serializer_class = api_serializers.POITypeSerializer
    queryset = trekking_models.POIType.objects.all()


class AccessibilityViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.GeotrekRelatedPortalTrekFilter,)
    serializer_class = api_serializers.AccessibilitySerializer

    def get_queryset(self):
        qs = trekking_models.Accessibility.objects.all()
        return filter_queryset_related_objects_published(qs, self.request, 'treks')


class RouteViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.GeotrekRelatedPortalTrekFilter,)
    serializer_class = api_serializers.RouteSerializer

    def get_queryset(self):
        qs = trekking_models.Route.objects.all()
        return filter_queryset_related_objects_published(qs, self.request, 'treks')
