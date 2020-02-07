from mapentity.views import (MapEntityLayer, MapEntityList, MapEntityJsonList, MapEntityFormat,
                             MapEntityDetail, MapEntityDocument, MapEntityCreate, MapEntityUpdate, MapEntityDelete)

from geotrek.core.models import AltimetryMixin
from geotrek.core.views import CreateFromTopologyMixin
from .models import (PhysicalEdge, LandEdge, CompetenceEdge,
                     WorkManagementEdge, SignageManagementEdge)
from .filters import PhysicalEdgeFilterSet, LandEdgeFilterSet, CompetenceEdgeFilterSet, WorkManagementEdgeFilterSet, SignageManagementEdgeFilterSet
from .forms import PhysicalEdgeForm, LandEdgeForm, CompetenceEdgeForm, WorkManagementEdgeForm, SignageManagementEdgeForm


class PhysicalEdgeLayer(MapEntityLayer):
    model = PhysicalEdge
    properties = ['color_index', 'name']


class PhysicalEdgeList(MapEntityList):
    model = PhysicalEdge
    filterform = PhysicalEdgeFilterSet
    columns = ['id', 'physical_type', 'length']


class PhysicalEdgeJsonList(MapEntityJsonList, PhysicalEdgeList):
    pass


class PhysicalEdgeFormatList(MapEntityFormat, PhysicalEdgeList):
    columns = [
        'id', 'physical_type',
        'date_insert', 'date_update',
        'cities', 'districts', 'areas',
    ] + AltimetryMixin.COLUMNS


class PhysicalEdgeDetail(MapEntityDetail):
    model = PhysicalEdge


class PhysicalEdgeDocument(MapEntityDocument):
    model = PhysicalEdge


class PhysicalEdgeCreate(CreateFromTopologyMixin, MapEntityCreate):
    model = PhysicalEdge
    form_class = PhysicalEdgeForm


class PhysicalEdgeUpdate(MapEntityUpdate):
    model = PhysicalEdge
    form_class = PhysicalEdgeForm


class PhysicalEdgeDelete(MapEntityDelete):
    model = PhysicalEdge


class LandEdgeLayer(MapEntityLayer):
    model = LandEdge
    properties = ['color_index', 'name']


class LandEdgeList(MapEntityList):
    model = LandEdge
    filterform = LandEdgeFilterSet
    columns = ['id', 'land_type', 'length']


class LandEdgeJsonList(MapEntityJsonList, LandEdgeList):
    pass


class LandEdgeFormatList(MapEntityFormat, LandEdgeList):
    columns = [
        'id', 'land_type', 'owner', 'agreement',
        'date_insert', 'date_update',
        'cities', 'districts', 'areas',
    ] + AltimetryMixin.COLUMNS


class LandEdgeDetail(MapEntityDetail):
    model = LandEdge


class LandEdgeDocument(MapEntityDocument):
    model = LandEdge


class LandEdgeCreate(CreateFromTopologyMixin, MapEntityCreate):
    model = LandEdge
    form_class = LandEdgeForm


class LandEdgeUpdate(MapEntityUpdate):
    model = LandEdge
    form_class = LandEdgeForm


class LandEdgeDelete(MapEntityDelete):
    model = LandEdge


class CompetenceEdgeLayer(MapEntityLayer):
    model = CompetenceEdge
    properties = ['color_index', 'name']


class CompetenceEdgeList(MapEntityList):
    model = CompetenceEdge
    filterform = CompetenceEdgeFilterSet
    columns = ['id', 'organization', 'length']


class CompetenceEdgeJsonList(MapEntityJsonList, CompetenceEdgeList):
    pass


class CompetenceEdgeFormatList(MapEntityFormat, CompetenceEdgeList):
    columns = [
        'id', 'organization',
        'date_insert', 'date_update',
        'cities', 'districts', 'areas',
    ] + AltimetryMixin.COLUMNS


class CompetenceEdgeDetail(MapEntityDetail):
    model = CompetenceEdge


class CompetenceEdgeDocument(MapEntityDocument):
    model = CompetenceEdge


class CompetenceEdgeCreate(CreateFromTopologyMixin, MapEntityCreate):
    model = CompetenceEdge
    form_class = CompetenceEdgeForm


class CompetenceEdgeUpdate(MapEntityUpdate):
    model = CompetenceEdge
    form_class = CompetenceEdgeForm


class CompetenceEdgeDelete(MapEntityDelete):
    model = CompetenceEdge


class WorkManagementEdgeLayer(MapEntityLayer):
    model = WorkManagementEdge
    properties = ['color_index', 'name']


class WorkManagementEdgeList(MapEntityList):
    model = WorkManagementEdge
    filterform = WorkManagementEdgeFilterSet
    columns = ['id', 'organization', 'length']


class WorkManagementEdgeJsonList(MapEntityJsonList, WorkManagementEdgeList):
    pass


class WorkManagementEdgeFormatList(MapEntityFormat, WorkManagementEdgeList):
    columns = [
        'id', 'organization',
        'date_insert', 'date_update',
        'cities', 'districts', 'areas',
    ] + AltimetryMixin.COLUMNS


class WorkManagementEdgeDetail(MapEntityDetail):
    model = WorkManagementEdge


class WorkManagementEdgeDocument(MapEntityDocument):
    model = WorkManagementEdge


class WorkManagementEdgeCreate(CreateFromTopologyMixin, MapEntityCreate):
    model = WorkManagementEdge
    form_class = WorkManagementEdgeForm


class WorkManagementEdgeUpdate(MapEntityUpdate):
    model = WorkManagementEdge
    form_class = WorkManagementEdgeForm


class WorkManagementEdgeDelete(MapEntityDelete):
    model = WorkManagementEdge


class SignageManagementEdgeLayer(MapEntityLayer):
    model = SignageManagementEdge
    properties = ['color_index', 'name']


class SignageManagementEdgeList(MapEntityList):
    model = SignageManagementEdge
    filterform = SignageManagementEdgeFilterSet
    columns = ['id', 'organization', 'length']


class SignageManagementEdgeJsonList(MapEntityJsonList, SignageManagementEdgeList):
    pass


class SignageManagementEdgeFormatList(MapEntityFormat, SignageManagementEdgeList):
    columns = [
        'id', 'organization',
        'date_insert', 'date_update',
        'cities', 'districts', 'areas',
    ] + AltimetryMixin.COLUMNS


class SignageManagementEdgeDetail(MapEntityDetail):
    model = SignageManagementEdge


class SignageManagementEdgeDocument(MapEntityDocument):
    model = SignageManagementEdge


class SignageManagementEdgeCreate(CreateFromTopologyMixin, MapEntityCreate):
    model = SignageManagementEdge
    form_class = SignageManagementEdgeForm


class SignageManagementEdgeUpdate(MapEntityUpdate):
    model = SignageManagementEdge
    form_class = SignageManagementEdgeForm


class SignageManagementEdgeDelete(MapEntityDelete):
    model = SignageManagementEdge
