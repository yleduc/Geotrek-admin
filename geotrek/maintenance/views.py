import logging

from django.utils.translation import ugettext_lazy as _
from mapentity.views import (MapEntityLayer, MapEntityList, MapEntityJsonList, MapEntityFormat, MapEntityViewSet,
                             MapEntityDetail, MapEntityDocument, MapEntityCreate, MapEntityUpdate, MapEntityDelete)

from geotrek.core.views import CreateFromTopologyMixin
from geotrek.altimetry.models import AltimetryMixin
from geotrek.common.views import FormsetMixin
from geotrek.authent.decorators import same_structure_required
from geotrek.infrastructure.models import Infrastructure
from geotrek.signage.models import Signage
from .models import Intervention, Project
from .filters import InterventionFilterSet, ProjectFilterSet
from .forms import (InterventionForm, InterventionCreateForm, ProjectForm,
                    FundingFormSet, ManDayFormSet)
from .serializers import InterventionSerializer, ProjectSerializer
from rest_framework import permissions as rest_permissions


logger = logging.getLogger(__name__)


class InterventionLayer(MapEntityLayer):
    model = Intervention
    properties = ['name']


class InterventionList(MapEntityList):
    model = Intervention
    filterform = InterventionFilterSet
    columns = ['id', 'name', 'date', 'type', 'infrastructure', 'status', 'stake']


class InterventionJsonList(MapEntityJsonList, InterventionList):
    pass


class InterventionFormatList(MapEntityFormat, InterventionList):
    columns = [
        'id', 'name', 'date', 'type', 'infrastructure', 'status', 'stake',
        'disorders', 'total_manday', 'project', 'subcontracting',
        'width', 'height', 'length', 'area', 'structure',
        'description', 'date_insert', 'date_update',
        'material_cost', 'heliport_cost', 'subcontract_cost',
        'total_cost_mandays', 'total_cost',
        'cities', 'districts', 'areas',
    ] + AltimetryMixin.COLUMNS


class InterventionDetail(MapEntityDetail):
    model = Intervention

    def get_context_data(self, *args, **kwargs):
        context = super(InterventionDetail, self).get_context_data(*args, **kwargs)
        context['can_edit'] = self.get_object().same_structure(self.request.user)
        return context


class InterventionDocument(MapEntityDocument):
    model = Intervention


class ManDayFormsetMixin(FormsetMixin):
    context_name = 'manday_formset'
    formset_class = ManDayFormSet


class InterventionCreate(ManDayFormsetMixin, CreateFromTopologyMixin, MapEntityCreate):
    model = Intervention
    form_class = InterventionCreateForm

    def on_infrastucture(self):
        pk_infra = self.request.GET.get('infrastructure')
        if pk_infra:
            try:
                return Infrastructure.objects.get(pk=pk_infra)
            except Infrastructure.DoesNotExist:
                logger.warning("Intervention on unknown infrastructure %s" % pk_infra)

    def on_signage(self):
        pk_signa = self.request.GET.get('signage')
        if pk_signa:
            try:
                return Signage.objects.get(pk=pk_signa)
            except Signage.DoesNotExist:
                logger.warning("Intervention on unknown signage %s" % pk_signa)
        return None

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super(InterventionCreate, self).get_initial()
        infrastructure = self.on_infrastucture()
        signage = self.on_signage()
        if infrastructure:
            # Create intervention on an infrastructure
            initial['infrastructure'] = infrastructure
        elif signage:
            # Create intervention on a signage
            initial['signage'] = signage
        return initial


class InterventionUpdate(ManDayFormsetMixin, MapEntityUpdate):
    model = Intervention
    form_class = InterventionForm

    @same_structure_required('maintenance:intervention_detail')
    def dispatch(self, *args, **kwargs):
        return super(InterventionUpdate, self).dispatch(*args, **kwargs)


class InterventionDelete(MapEntityDelete):
    model = Intervention

    @same_structure_required('maintenance:intervention_detail')
    def dispatch(self, *args, **kwargs):
        return super(InterventionDelete, self).dispatch(*args, **kwargs)


class InterventionViewSet(MapEntityViewSet):
    model = Intervention
    model = Intervention
    serializer_class = InterventionSerializer
    permission_classes = [rest_permissions.DjangoModelPermissionsOrAnonReadOnly]


class ProjectLayer(MapEntityLayer):
    model = Project
    properties = ['name']

    def get_queryset(self):
        nonemptyqs = Intervention.objects.filter(project__isnull=False).values('project')
        return super(ProjectLayer, self).get_queryset().filter(pk__in=nonemptyqs)


class ProjectList(MapEntityList):
    model = Project
    filterform = ProjectFilterSet
    columns = ['id', 'name', 'period', 'type', 'domain']


class ProjectJsonList(MapEntityJsonList, ProjectList):
    pass


class ProjectFormatList(MapEntityFormat, ProjectList):
    columns = [
        'id', 'structure', 'name', 'period', 'type', 'domain', 'constraint', 'global_cost',
        'interventions', 'interventions_total_cost', 'comments', 'contractors',
        'project_owner', 'project_manager', 'founders',
        'date_insert', 'date_update',
        'cities', 'districts', 'areas',
    ]


class ProjectDetail(MapEntityDetail):
    model = Project

    def get_context_data(self, *args, **kwargs):
        context = super(ProjectDetail, self).get_context_data(*args, **kwargs)
        context['can_edit'] = self.get_object().same_structure(self.request.user)
        context['empty_map_message'] = _("No intervention related.")
        return context


class ProjectDocument(MapEntityDocument):
    model = Project


class FundingFormsetMixin(FormsetMixin):
    context_name = 'funding_formset'
    formset_class = FundingFormSet


class ProjectCreate(FundingFormsetMixin, MapEntityCreate):
    model = Project
    form_class = ProjectForm


class ProjectUpdate(FundingFormsetMixin, MapEntityUpdate):
    model = Project
    form_class = ProjectForm

    @same_structure_required('maintenance:project_detail')
    def dispatch(self, *args, **kwargs):
        return super(ProjectUpdate, self).dispatch(*args, **kwargs)


class ProjectDelete(MapEntityDelete):
    model = Project

    @same_structure_required('maintenance:project_detail')
    def dispatch(self, *args, **kwargs):
        return super(ProjectDelete, self).dispatch(*args, **kwargs)


class ProjectViewSet(MapEntityViewSet):
    model = Project
    model = Project
    serializer_class = ProjectSerializer
    permission_classes = [rest_permissions.DjangoModelPermissionsOrAnonReadOnly]
