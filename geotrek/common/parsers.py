import os
import re
import requests
import logging
from requests.auth import HTTPBasicAuth
import textwrap
import xlrd
import xml.etree.ElementTree as ET
from functools import reduce
from collections import Iterable
from time import sleep

from ftplib import FTP
from os.path import dirname
from urllib.parse import urlparse

from django.db import models, connection
from django.db.utils import DatabaseError, InternalError
from django.contrib.auth import get_user_model
from django.contrib.gis.gdal import DataSource, GDALException, CoordTransform
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.encoding import force_str
from django.conf import settings
from paperclip.models import attachment_upload

from geotrek.authent.models import default_structure
from geotrek.common.models import FileType, Attachment
from geotrek.common.utils.translation import get_translated_fields

if 'modeltranslation' in settings.INSTALLED_APPS:
    from modeltranslation.fields import TranslationField

logger = logging.getLogger(__name__)


class ImportError(Exception):
    pass


class GlobalImportError(ImportError):
    pass


class RowImportError(ImportError):
    pass


class ValueImportError(ImportError):
    pass


class DownloadImportError(ImportError):
    pass


class Parser:
    label = None
    model = None
    filename = None
    url = None
    simplify_tolerance = 0  # meters
    update_only = False
    delete = False
    duplicate_eid_allowed = False
    warn_on_missing_fields = False
    warn_on_missing_objects = False
    separator = '+'
    eid = None
    fields = None
    m2m_fields = {}
    constant_fields = {}
    m2m_constant_fields = {}
    m2m_aggregate_fields = []
    non_fields = {}
    natural_keys = {}
    field_options = {}

    def __init__(self, progress_cb=None, user=None, encoding='utf8'):
        self.warnings = {}
        self.line = 0
        self.nb_success = 0
        self.nb_created = 0
        self.nb_updated = 0
        self.nb_unmodified = 0
        self.progress_cb = progress_cb
        self.user = user
        self.structure = user and user.profile.structure or default_structure()
        self.encoding = encoding
        self.translated_fields = get_translated_fields(self.model)

        if self.fields is None:
            self.fields = {
                f.name: force_str(f.verbose_name)
                for f in self.model._meta.fields
                if not isinstance(f, TranslationField)
            }
            self.m2m_fields = {
                f.name: force_str(f.verbose_name)
                for f in self.model._meta.many_to_many
            }

    def normalize_field_name(self, name):
        return name.upper()

    def normalize_src(self, src):
        if isinstance(src, Iterable) and not isinstance(src, str):
            return [self.normalize_field_name(subsrc) for subsrc in src]
        else:
            return self.normalize_field_name(src)

    def add_warning(self, msg):
        key = _("Line {line}".format(line=self.line))
        warnings = self.warnings.setdefault(key, [])
        warnings.append(msg)

    def get_part(self, dst, src, val):
        if not src:
            return val
        if val is None:
            return None
        if '.' in src:
            part, left = src.split('.', 1)
        else:
            part, left = src, ''
        try:
            value = int(part)
            return self.get_part(dst, left, val[value])
        except ValueError:
            if part == '*':
                return [self.get_part(dst, left, subval) for subval in val]
            else:
                return self.get_part(dst, left, val[part])

    def get_val(self, row, dst, src):
        if isinstance(src, Iterable) and not isinstance(src, str):
            val = []
            for subsrc in src:
                try:
                    val.append(self.get_val(row, dst, subsrc))
                except ValueImportError as warning:
                    if self.warn_on_missing_fields:
                        self.add_warning(str(warning))
                    val.append(None)
            return val
        else:
            try:
                return self.get_part(dst, src, row)
            except (KeyError, IndexError):
                required = "required " if self.field_options.get(dst, {}).get('required', False) else ""
                raise ValueImportError(_("Missing {required}field '{src}'").format(required=required, src=src))

    def apply_filter(self, dst, src, val):
        field = self.model._meta.get_field(dst)
        if (isinstance(field, models.ForeignKey) or isinstance(field, models.ManyToManyField)):
            if dst not in self.natural_keys:
                raise ValueImportError(_("Destination field '{dst}' not in natural keys configuration").format(dst=dst))
            to = field.remote_field.model
            natural_key = self.natural_keys[dst]
            kwargs = self.field_options.get(dst, {})
            if isinstance(field, models.ForeignKey):
                val = self.filter_fk(src, val, to, natural_key, **kwargs)
            else:
                val = self.filter_m2m(src, val, to, natural_key, **kwargs)
        return val

    def parse_non_field(self, dst, src, val):
        """Returns True if modified"""
        if hasattr(self, 'save_{0}'.format(dst)):
            return getattr(self, 'save_{0}'.format(dst))(src, val)

    def set_value(self, dst, src, val):
        field = self.model._meta.get_field(dst)
        if val is None and not field.null:
            if field.blank and (isinstance(field, models.CharField) or isinstance(field, models.TextField)):
                val = ""
            else:
                raise RowImportError(_("Null value not allowed for field '{src}'".format(src=src)))
        if val == "" and not field.blank:
            raise RowImportError(_("Blank value not allowed for field '{src}'".format(src=src)))
        if isinstance(field, models.CharField):
            val = str(val)[:256]
        if isinstance(field, models.ManyToManyField):
            fk = getattr(self.obj, dst)
            fk.set(val)
        else:
            setattr(self.obj, dst, val)

    def parse_real_field(self, dst, src, val):
        """Returns True if modified"""
        if hasattr(self, 'filter_{0}'.format(dst)):
            val = getattr(self, 'filter_{0}'.format(dst))(src, val)
        else:
            val = self.apply_filter(dst, src, val)
        if hasattr(self.obj, dst):
            if dst in self.m2m_fields or dst in self.m2m_constant_fields:
                old = set(getattr(self.obj, dst).all())
                val = set(val)
                if dst in self.m2m_aggregate_fields:
                    val = val | old
            else:
                old = getattr(self.obj, dst)
            if isinstance(old, float) and isinstance(val, float):
                old = round(old, 10)
                val = round(val, 10)
            if isinstance(old, str):
                val = val or ""
            if old != val:
                self.set_value(dst, src, val)
                return True
            else:
                return False
        else:
            self.set_value(dst, src, val)
            return True

    def parse_field(self, row, dst, src, updated, non_field):
        if dst in self.constant_fields:
            val = self.constant_fields[dst]
        elif dst in self.m2m_constant_fields:
            val = self.m2m_constant_fields[dst]
        else:
            src = self.normalize_src(src)
            val = self.get_val(row, dst, src)
        if non_field:
            modified = self.parse_non_field(dst, src, val)
        else:
            modified = self.parse_real_field(dst, src, val)
        if modified:
            updated.append(dst)
            if dst in self.translated_fields:
                lang = translation.get_language()
                updated.append('{field}_{lang}'.format(field=dst, lang=lang))

    def parse_fields(self, row, fields, non_field=False):
        updated = []
        for dst, src in fields.items():
            try:
                self.parse_field(row, dst, src, updated, non_field)
            except ValueImportError as warning:
                if self.field_options.get(dst, {}).get('required', False):
                    raise RowImportError(warning)
                if self.warn_on_missing_fields:
                    self.add_warning(str(warning))
                continue
        return updated

    def parse_obj(self, row, operation):
        try:
            update_fields = self.parse_fields(row, self.fields)
            update_fields += self.parse_fields(row, self.constant_fields)
            if 'id' in update_fields:
                update_fields.remove('id')  # Can't update primary key
        except RowImportError as warnings:
            self.add_warning(str(warnings))
            return
        if operation == "created":
            self.obj.save()
        else:
            self.obj.save(update_fields=update_fields)
        update_fields += self.parse_fields(row, self.m2m_fields)
        update_fields += self.parse_fields(row, self.m2m_constant_fields)
        update_fields += self.parse_fields(row, self.non_fields, non_field=True)
        if operation == "created":
            self.nb_created += 1
        elif update_fields:
            self.nb_updated += 1
        else:
            self.nb_unmodified += 1

    def get_eid_kwargs(self, row):
        try:
            eid_src = self.fields[self.eid]
        except KeyError:
            raise GlobalImportError(_("Eid field '{eid_dst}' missing in parser configuration").format(eid_dst=self.eid))
        eid_src = self.normalize_field_name(eid_src)
        try:
            eid_val = self.get_val(row, self.eid, eid_src)
        except KeyError:
            raise GlobalImportError(_("Missing id field '{eid_src}'").format(eid_src=eid_src))
        if hasattr(self, 'filter_{0}'.format(self.eid)):
            eid_val = getattr(self, 'filter_{0}'.format(self.eid))(eid_src, eid_val)
        self.eid_src = eid_src
        self.eid_val = eid_val
        return {self.eid: eid_val}

    def parse_row(self, row):
        self.eid_val = None
        self.line += 1
        if self.eid is None:
            eid_kwargs = {}
            objects = self.model.objects.none()
        else:
            try:
                eid_kwargs = self.get_eid_kwargs(row)
            except RowImportError as warnings:
                self.add_warning(str(warnings))
                return
            objects = self.model.objects.filter(**eid_kwargs)
        if len(objects) == 0 and self.update_only:
            if self.warn_on_missing_objects:
                self.add_warning(_("Bad value '{eid_val}' for field '{eid_src}'. No object with this identifier").format(eid_val=self.eid_val, eid_src=self.eid_src))
            return
        elif len(objects) == 0:
            obj = self.model(**eid_kwargs)
            if hasattr(obj, 'structure'):
                obj.structure = self.structure
            objects = [obj]
            operation = "created"
        elif len(objects) >= 2 and not self.duplicate_eid_allowed:
            self.add_warning(_("Bad value '{eid_val}' for field '{eid_src}'. Multiple objects with this identifier").format(eid_val=self.eid_val, eid_src=self.eid_src))
            return
        else:
            _objects = []
            for obj in objects:
                if not hasattr(obj, 'structure') or obj.structure == self.structure or self.user is None or self.user.has_perm('authent.can_bypass_structure'):
                    _objects.append(obj)
                else:
                    self.to_delete.discard(obj.pk)
                    self.add_warning(_("Bad ownership '{structure}' for object '{eid_val}'.").format(structure=obj.structure.name, eid_val=self.eid_val))
            objects = _objects
            operation = "updated"
        for self.obj in objects:
            self.parse_obj(row, operation)
            self.to_delete.discard(self.obj.pk)
        self.nb_success += 1  # FIXME
        if self.progress_cb:
            self.progress_cb(float(self.line) / self.nb, self.line, self.eid_val)

    def report(self, output_format='txt'):
        context = {
            'nb_success': self.nb_success,
            'nb_lines': self.line,
            'nb_created': self.nb_created,
            'nb_updated': self.nb_updated,
            'nb_deleted': len(self.to_delete) if self.delete else None,
            'nb_unmodified': self.nb_unmodified,
            'warnings': self.warnings,
        }
        return render_to_string('common/parser_report.{output_format}'.format(output_format=output_format), context)

    def get_mapping(self, src, val, mapping, partial):
        if partial:
            found = False
            for i, j in mapping.items():
                if i in val:
                    val = j
                    found = True
                    break
            if not found:
                self.add_warning(_("Bad value '{val}' for field {src}. Should contain {values}").format(val=val, src=src, separator=self.separator, values=', '.join(mapping.keys())))
                return None
        else:
            if mapping is not None:
                if val not in mapping.keys():
                    self.add_warning(_("Bad value '{val}' for field {src}. Should be {values}").format(val=val, src=src, separator=self.separator, values=', '.join(mapping.keys())))
                    return None
                val = mapping[val]
        return val

    def filter_fk(self, src, val, model, field, mapping=None, partial=False, create=False, fk=None, **kwargs):
        val = self.get_mapping(src, val, mapping, partial)
        if val is None:
            return None
        fields = {field: val}
        if fk:
            fields[fk] = getattr(self.obj, fk)
        if create:
            val, created = model.objects.get_or_create(**fields)
            if created:
                self.add_warning(_("{model} '{val}' did not exist in Geotrek-Admin and was automatically created").format(model=model._meta.verbose_name.title(), val=val))
            return val
        try:
            return model.objects.get(**fields)
        except model.DoesNotExist:
            self.add_warning(_("{model} '{val}' does not exists in Geotrek-Admin. Please add it").format(model=model._meta.verbose_name.title(), val=val))
            return None

    def filter_m2m(self, src, val, model, field, mapping=None, partial=False, create=False, fk=None, **kwargs):
        if not val:
            return []
        if self.separator and not isinstance(val, list):
            val = val.split(self.separator)
        dst = []
        for subval in val:
            subval = subval.strip()
            subval = self.get_mapping(src, subval, mapping, partial)
            if subval is None:
                continue
            fields = {field: subval}
            if fk:
                fields[fk] = getattr(self.obj, fk)
            if create:
                subval, created = model.objects.get_or_create(**fields)
                if created:
                    self.add_warning(_("{model} '{val}' did not exist in Geotrek-Admin and was automatically created").format(model=model._meta.verbose_name.title(), val=subval))
                dst.append(subval)
                continue
            try:
                dst.append(model.objects.get(**fields))
            except model.DoesNotExist:
                self.add_warning(_("{model} '{val}' does not exists in Geotrek-Admin. Please add it").format(model=model._meta.verbose_name.title(), val=subval))
                continue
        return dst

    def get_to_delete_kwargs(self):
        # FIXME: use mapping if it exists
        kwargs = {}
        for dst, val in self.constant_fields.items():
            field = self.model._meta.get_field(dst)
            if isinstance(field, models.ForeignKey):
                natural_key = self.natural_keys[dst]
                try:
                    kwargs[dst] = field.remote_field.model.objects.get(**{natural_key: val})
                except field.remote_field.model.DoesNotExist:
                    return None
            else:
                kwargs[dst] = val
        for dst, val in self.m2m_constant_fields.items():
            assert not self.separator or self.separator not in val
            field = self.model._meta.get_field(dst)
            natural_key = self.natural_keys[dst]
            filters = {natural_key: subval for subval in val}
            if not filters:
                continue
            try:
                kwargs[dst] = field.remote_field.model.objects.get(**filters)
            except field.remote_field.model.DoesNotExist:
                return None
        return kwargs

    def start(self):
        kwargs = self.get_to_delete_kwargs()
        if kwargs is None:
            self.to_delete = set()
        else:
            self.to_delete = set(self.model.objects.filter(**kwargs).values_list('pk', flat=True))

    def end(self):
        if self.delete:
            self.model.objects.filter(pk__in=self.to_delete).delete()

    def parse(self, filename=None, limit=None):
        if filename:
            self.filename = filename
        if not self.url and not self.filename:
            raise GlobalImportError(_("Filename is required"))
        if self.filename and not os.path.exists(self.filename):
            raise GlobalImportError(_("File does not exists at: {filename}").format(filename=self.filename))
        self.start()
        for i, row in enumerate(self.next_row()):
            if limit and i >= limit:
                break
            try:
                self.parse_row(row)
            except DatabaseError as e:
                if settings.DEBUG:
                    raise
                self.add_warning(str(e))
            except (ValueImportError, RowImportError) as e:
                self.add_warning(str(e))
            except Exception as e:
                raise
                if settings.DEBUG:
                    raise
                self.add_warning(str(e))
        self.end()

    def request_or_retry(self, url, verb='get', **kwargs):
        try_get = settings.PARSER_NUMBER_OF_TRIES
        assert try_get > 0
        while try_get:
            action = getattr(requests, verb)
            response = action(url, allow_redirects=True, **kwargs)
            if response.status_code in settings.PARSER_RETRY_HTTP_STATUS:
                logger.info("Failed to fetch url {}. Retrying ...".format(url))
                sleep(settings.PARSER_RETRY_SLEEP_TIME)
                try_get -= 1
            elif response.status_code == 200:
                return response
            else:
                break
        logger.warning("Failed to fetch {} after {} times. Status code : {}.".format(url, settings.PARSER_NUMBER_OF_TRIES, response.status_code))
        raise DownloadImportError(_("Failed to download {url}. HTTP status code {status_code}").format(url=response.url, status_code=response.status_code))


class XmlParser(Parser):
    """XML Parser"""
    ns = {}
    results_path = ''

    def next_row(self):
        if self.filename:
            with open(self.filename) as f:
                self.root = ET.fromstring(f.read())
        else:
            response = requests.get(self.url, params={})
            if response.status_code != 200:
                raise GlobalImportError(_(u"Failed to download {url}. HTTP status code {status_code}").format(
                    url=self.url, status_code=response.status_code))
            self.root = ET.fromstring(response.content)
        entries = self.root.findall(self.results_path, self.ns)
        self.nb = len(entries)
        for row in entries:
            yield row

    def get_part(self, dst, src, val):
        return val.findtext(src, None, self.ns)

    def normalize_field_name(self, name):
        return name


class ShapeParser(Parser):
    def next_row(self):
        datasource = DataSource(self.filename, encoding=self.encoding)
        layer = datasource[0]
        SpatialRefSys = connection.ops.spatial_ref_sys()
        target_srs = SpatialRefSys.objects.get(srid=settings.SRID).srs
        coord_transform = CoordTransform(layer.srs, target_srs)
        self.nb = len(layer)
        for i, feature in enumerate(layer):
            row = {self.normalize_field_name(field.name): field.value for field in feature}
            try:
                ogrgeom = feature.geom
            except GDALException:
                print(_("Invalid geometry pointer"), i)
                geom = None
            else:
                ogrgeom.coord_dim = 2  # Flatten to 2D
                ogrgeom.transform(coord_transform)
                geom = ogrgeom.geos
            if self.simplify_tolerance and geom is not None:
                geom = geom.simplify(self.simplify_tolerance)
            row[self.normalize_field_name('geom')] = geom
            yield row

    def normalize_field_name(self, name):
        """Shapefile field names length is 10 char max"""
        name = super().normalize_field_name(name)
        return name[:10]


class ExcelParser(Parser):
    def next_row(self):
        workbook = xlrd.open_workbook(self.filename)
        sheet = workbook.sheet_by_index(0)
        header = [self.normalize_field_name(cell.value) for cell in sheet.row(0)]
        self.nb = sheet.nrows - 1
        for i in range(1, sheet.nrows):
            values = [cell.value for cell in sheet.row(i)]
            row = dict(zip(header, values))
            yield row


class AtomParser(Parser):
    ns = {
        'Atom': 'http://www.w3.org/2005/Atom',
        'georss': 'http://www.georss.org/georss',
    }

    def flatten_fields(self, fields):
        return reduce(lambda x, y: x + (list(y) if hasattr(y, '__iter__') else [y]), fields.values(), [])

    def next_row(self):
        srcs = self.flatten_fields(self.fields)
        srcs += self.flatten_fields(self.m2m_fields)
        srcs += self.flatten_fields(self.non_fields)
        tree = ET.parse(self.filename)
        entries = tree.getroot().findall('Atom:entry', self.ns)
        self.nb = len(entries)
        for entry in entries:
            row = {self.normalize_field_name(src): entry.find(src, self.ns).text for src in srcs}
            yield row


class AttachmentParserMixin:
    download_attachments = True
    base_url = ''
    delete_attachments = True
    filetype_name = "Photographie"
    non_fields = {
        'attachments': _("Attachments"),
    }

    def start(self):
        super().start()
        if settings.PAPERCLIP_ENABLE_LINK is False and self.download_attachments is False:
            raise Exception('You need to enable PAPERCLIP_ENABLE_LINK to use this function')
        try:
            self.filetype = FileType.objects.get(type=self.filetype_name, structure=None)
        except FileType.DoesNotExist:
            try:
                self.filetype = FileType.objects.get(type=self.filetype_name, structure=self.structure)
            except FileType.DoesNotExist:
                raise GlobalImportError(_("FileType '{name}' does not exists in "
                                          "Geotrek-Admin. Please add it").format(name=self.filetype_name))
        self.creator, created = get_user_model().objects.get_or_create(username='import', defaults={'is_active': False})

    def filter_attachments(self, src, val):
        if not val:
            return []
        return [(subval.strip(), '', '') for subval in val.split(self.separator) if subval.strip()]

    def has_size_changed(self, url, attachment):
        parsed_url = urlparse(url)
        if parsed_url.scheme == 'ftp':
            directory = dirname(parsed_url.path)

            ftp = FTP(parsed_url.hostname)
            ftp.login(user=parsed_url.username, passwd=parsed_url.password)
            ftp.cwd(directory)
            size = ftp.size(parsed_url.path.split('/')[-1:][0])
            return size != attachment.attachment_file.size

        if parsed_url.scheme == 'http' or parsed_url.scheme == 'https':
            try:
                response = self.request_or_retry(url, verb='head')
            except DownloadImportError as e:
                raise ValueImportError('Failed to load attachment: {exc}'.format(exc=e))
            size = response.headers.get('content-length')
            return size is not None and int(size) != attachment.attachment_file.size

        return True

    def download_attachment(self, url):
        parsed_url = urlparse(url)
        if parsed_url.scheme == 'ftp':
            try:
                response = self.request_or_retry(url)
            except DownloadImportError as e:
                raise ValueImportError('Failed to load attachment: {exc}'.format(exc=e))
            return response.read()
        else:
            if self.download_attachments:
                try:
                    response = self.request_or_retry(url)
                except DownloadImportError as e:
                    raise ValueImportError('Failed to load attachment: {exc}'.format(exc=e))
                if response.status_code != requests.codes.ok:
                    self.add_warning(_("Failed to download '{url}'").format(url=url))
                    return None
                return response.content
            return None

    def save_attachments(self, src, val):
        updated = False
        attachments_to_delete = list(Attachment.objects.attachments_for_object(self.obj))
        for url, legend, author in self.filter_attachments(src, val):
            url = self.base_url + url
            legend = legend or ""
            author = author or ""
            basename, ext = os.path.splitext(os.path.basename(url))
            name = '%s%s' % (basename[:128], ext)
            found = False
            for attachment in attachments_to_delete:
                upload_name, ext = os.path.splitext(attachment_upload(attachment, name))
                existing_name = attachment.attachment_file.name
                if re.search(r"^{name}(_[a-zA-Z0-9]{{7}})?{ext}$".format(
                        name=upload_name, ext=ext), existing_name
                ) and not self.has_size_changed(url, attachment):
                    found = True
                    attachments_to_delete.remove(attachment)
                    if author != attachment.author or legend != attachment.legend:
                        attachment.author = author
                        attachment.legend = textwrap.shorten(legend, width=127)
                        attachment.save()
                        updated = True
                    break
            if found:
                continue

            parsed_url = urlparse(url)

            attachment = Attachment()
            attachment.content_object = self.obj
            attachment.filetype = self.filetype
            attachment.creator = self.creator
            attachment.author = author
            attachment.legend = textwrap.shorten(legend, width=127)

            if (parsed_url.scheme in ('http', 'https') and self.download_attachments) or parsed_url.scheme == 'ftp':
                content = self.download_attachment(url)
                if content is None:
                    continue
                f = ContentFile(content)
                attachment.attachment_file.save(name, f, save=False)
            else:
                attachment.attachment_link = url
            attachment.save()
            updated = True

        if self.delete_attachments:
            for att in attachments_to_delete:
                att.delete()
        return updated


class TourInSoftParser(AttachmentParserMixin, Parser):
    version_tourinsoft = 2
    separator = '#'
    separator2 = '|'

    @property
    def items(self):
        if self.version_tourinsoft == 3:
            return self.root['value']
        return self.root['d']['results']

    def get_nb(self):
        if self.version_tourinsoft == 3:
            return int(self.root['odata.count'])
        return int(self.root['d']['__count'])

    def next_row(self):
        skip = 0
        while True:
            params = {
                '$format': 'json',
                '$inlinecount': 'allpages',
                '$top': 1000,
                '$skip': skip,
            }
            response = self.request_or_retry(self.url, params=params)
            self.root = response.json()
            self.nb = self.get_nb()
            for row in self.items:
                yield {self.normalize_field_name(src): val for src, val in row.items()}
            skip += 1000
            if skip >= self.nb:
                return

    def filter_attachments(self, src, val):
        if not val:
            return []
        return [
            subval.split(self.separator2)
            for subval in val.split(self.separator)
            if subval.split(self.separator2)[0]
        ]

    def filter_geom(self, src, val):
        lng, lat = val
        if not lng or not lat:
            raise ValueImportError("Empty geometry")
        geom = Point(float(lng), float(lat), srid=4326)  # WGS84
        geom.transform(settings.SRID)
        return geom

    def filter_email(self, src, val):
        val = val or ""

        for subval in val.split(self.separator):
            if not subval:
                continue
            try:
                key, value = subval.split(self.separator2)
            except ValueError as e:
                raise ValueImportError("Fail to split <MoyenDeCom>: {}".format(e))
            if key in ("Mél", "Mail"):
                return value

        return ""

    def filter_website(self, src, val):
        val = val or ""

        for subval in val.split(self.separator):
            if not subval:
                continue
            try:
                key, value = subval.split(self.separator2)
            except ValueError as e:
                raise ValueImportError("Fail to split <MoyenDeCom>: {}".format(e))
            if key in ("Site web", "Site web (URL)"):
                return value

        return ""

    def filter_contact(self, src, val):
        com, adresse = val
        infos = []

        if adresse:
            # Some address have 6 items, some others 7 items :(
            lines = adresse.split(self.separator2)
            # Remove last field (code INSEE)
            lines = lines[:-1]
            # Put city and postal code together
            if lines[-2] and lines[-1]:
                lines[-2:] = [" ".join(lines[-2:])]
            # Remove empty lines
            lines = [line for line in lines if line]
            infos.append(
                "<strong>Adresse :</strong><br>"
                + "<br>".join(lines)
            )

        if com:
            for subval in com.split(self.separator):
                if not subval:
                    continue
                try:
                    key, value = subval.split(self.separator2)
                except ValueError as e:
                    raise ValueImportError("Fail to split <MoyenDeCom>: {}".format(e))
                if key in ("Mél", "Mail", "Site web", "Site web (URL)"):
                    continue
                infos.append("<strong>{} :</strong><br>{}".format(key, value))

        return "<br><br>".join(infos)


class TourismSystemParser(AttachmentParserMixin, Parser):
    @property
    def items(self):
        return self.root['data']

    def next_row(self):
        size = 1000
        skip = 0
        while True:
            params = {
                'size': size,
                'start': skip,
            }
            response = self.request_or_retry(self.url, params=params, authent=HTTPBasicAuth(self.login, self.password))
            self.root = response.json()
            self.nb = int(self.root['metadata']['total'])
            for row in self.items:
                yield {self.normalize_field_name(src): val for src, val in row.items()}
            skip += size
            if skip >= self.nb:
                return

    def filter_attachments(self, src, val):
        result = []
        for subval in val or []:
            try:
                name = subval['name']['fr']
            except KeyError:
                name = None
            result.append((subval['URL'], name, None))
        return result

    def normalize_field_name(self, name):
        return name


class OpenSystemParser(Parser):
    url = 'http://proxy-xml.open-system.fr/rest.aspx'

    def next_row(self):
        params = {
            'Login': self.login,
            'Pass': self.password,
            'Action': 'concentrateur_liaisons',
        }
        response = self.request_or_retry(self.url, params=params)
        self.root = ET.fromstring(response.content).find('Resultat').find('Objets')
        self.nb = len(self.root)
        for row in self.root:
            id_apidae = row.find('ObjetCle').find('Cle').text
            for liaison in row.find('Liaisons'):
                yield {
                    'id_apidae': id_apidae,
                    'id_opensystem': liaison.find('ObjetOS').find('CodeUI').text,
                }

    def normalize_field_name(self, name):
        return name


class LEIParser(AttachmentParserMixin, XmlParser):
    """
    Parser for LEI tourism SIT

    You can define :

    fields = {
        'eid': 'PRODUIT',
        'name': 'NOM',
        'description': 'COMMENTAIRE',
        'contact': (
            'ADRPROD_NUM_VOIE', 'ADRPROD_LIB_VOIE', 'ADRPROD_CP', 'ADRPROD_LIBELLE_COMMUNE',
            'ADRPROD_TEL', 'ADRPROD_TEL2', 'ADRPREST_TEL', 'ADRPREST_TEL2'
        ),
        'email': ('ADRPROD_EMAIL'),
        'website': ('ADRPROD_URL', 'ADRPREST_URL'),
        'geom': ('LATITUDE', 'LONGITUDE'),
    }

    non_fields = {
        'attachments': ('CRITERES/Crit[@CLEF_CRITERE="30000279"]', 'CRITERES/Crit[@CLEF_CRITERE="900003"]'),
    }
    """
    results_path = 'Resultat/sit_liste'
    eid = 'eid'

    def get_part(self, dst, src, val):
        """For generic CRITERES return XML Crit element"""
        if 'CRITERES/Crit' in src:
            # Return list of Crit elements
            return val.findall(src)
        return val.findtext(src, None, self.ns)

    def get_crit_kv(self, crit):
        """Get Crit key / value according to Nomenclature"""
        crit_name = self.root.findtext(
            'NOMENCLATURE/CRIT[@CLEF="{0}"]/NOMCRIT'.format(crit.attrib['CLEF_CRITERE'])
        )
        crit_value = self.get_crit_value(crit)

        # If value is available for crit, add it to result
        if crit.text is not None and crit_value != 'Photos':
            crit_value = "{0} : {1}".format(crit_value, crit.text)
        return crit_name, crit_value

    def get_crit_value(self, crit):
        """Get Crit value only, according to Nomenclature"""
        return self.root.findtext(
            'NOMENCLATURE/CRIT[@CLEF="{0}"]/MODAL[@CLEF="{1}"]'.format(
                crit.attrib['CLEF_CRITERE'],
                crit.attrib['CLEF_MODA']
            )
        )

    def start(self):
        super(LEIParser, self).start()
        lei = set(self.model.objects.filter(eid__startswith='LEI').values_list('pk', flat=True))
        self.to_delete = self.to_delete & lei

    def filter_eid(self, src, val):
        return 'LEI' + val

    def filter_attachments(self, src, val):
        """Get Photos url and legend from Crit element list

        Keyword arguments:
        src --
        val -- Crit element list

        returns photos list of tuples (url, legend, '')
        """
        photos = []
        for crit in val[0]:
            (url, legend) = crit.text, self.get_crit_value(crit)
            if not url:
                continue
            if legend:
                legend = legend[:128]
            url = url.replace('https://', 'http://')
            if url[:7] != 'http://':
                url = 'http://' + url
            photos.append((url, legend, ''))
        return photos

    def filter_description(self, src, val):
        if val is None:
            return ""
        val = val.replace('\n', '<br>')
        return val

    def filter_geom(self, src, val):
        lat, lng = val
        if lat is None or lng is None:
            raise ValueImportError("Missing {required}field '{src}'")
        lat = lat.replace(',', '.')
        lng = lng.replace(',', '.')
        geom = Point(float(lng), float(lat), srid=4326)  # WGS84
        try:
            geom.transform(settings.SRID)
        except InternalError as e:
            raise ValueImportError(e)
        if self.obj.geom and abs(geom.x - self.obj.geom.x) < 0.001 and abs(geom.y - self.obj.geom.y) < 0.001:
            return self.obj.geom
        return geom

    def filter_website(self, src, val):
        (val1, val2) = val
        if val1:
            if val1.startswith('http'):
                return val1
            else:
                return 'http://' + val1
        if val2:
            if val2.startswith('http'):
                return val2
            else:
                return 'http://' + val2
