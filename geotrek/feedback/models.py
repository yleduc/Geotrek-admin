import html
import json
import logging
from datetime import timedelta
from uuid import uuid4

from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.core.mail import mail_managers, send_mail
from django.db.models import F
from django.db.models.query_utils import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from mapentity.models import MapEntityMixin

from geotrek.common.mixins.models import AddPropertyMixin, NoDeleteMixin, PicturesMixin, TimeStampedModelMixin
from geotrek.common.utils import intersecting
from geotrek.core.models import Path
from geotrek.trekking.models import POI, Service, Trek
from geotrek.zoning.mixins import ZoningPropertiesMixin
from geotrek.zoning.models import District

from .helpers import SuricateMessenger

if 'geotrek.maintenance' in settings.INSTALLED_APPS:
    from geotrek.maintenance.models import Intervention

logger = logging.getLogger(__name__)


# This dict stores status changes that send an email and an API request
NOTIFY_SURICATE_AND_SENTINEL = {
    'filed': ['classified', 'waiting'],
    'solved_intervention': ['solved']
}

STATUS_WHEN_REPORT_IS_LATE = {
    'waiting': 'late_intervention',
    'programmed': 'late_resolution',
}


def status_default():
    """Set status to New by default"""
    new_status_query = ReportStatus.objects.filter(label="Nouveau")
    if new_status_query:
        return new_status_query.get().pk
    return None


class SelectableUserManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(userprofile__isnull=False)


class SelectableUser(User):

    objects = SelectableUserManager()

    class Meta:
        proxy = True

    def __str__(self):
        return f"{self.username} ({self.email})"


class RequestType(models.TextChoices):
    GET = 'GET', 'Get Request'
    POST = 'POST', 'Post Request'


class SuricateAPI(models.TextChoices):
    STANDARD = 'STA', 'Standard API'
    MANAGEMENT = 'MAN', 'Management API'


class PendingSuricateAPIRequest(models.Model):

    request_type = models.CharField(max_length=4, choices=RequestType.choices)
    api = models.CharField(max_length=3, choices=SuricateAPI.choices)
    endpoint = models.CharField(max_length=40, null=False, blank=False)
    params = models.JSONField(max_length=300, null=False, blank=False)
    error_message = models.TextField(null=False, blank=False)
    retries = models.IntegerField(blank=False, default=0)

    def raise_sync_error_flag_on_report(self, external_uuid):
        report = Report.objects.filter(external_uuid=external_uuid)
        report.update(sync_errors=F('sync_errors') + 1)

    def remove_sync_error_flag_on_report(self, external_uuid):
        report = Report.objects.filter(external_uuid=external_uuid)
        report.update(sync_errors=F('sync_errors') - 1)

    def save(self, *args, **kwargs):
        # Set sync_errors flag on report
        if 'uid_alerte' in self.params and not self.pk:
            uuid = json.loads(self.params)["uid_alerte"]
            self.raise_sync_error_flag_on_report(uuid)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Remove sync_errors flag from report
        if 'uid_alerte' in self.params:
            uuid = json.loads(self.params)["uid_alerte"]
            self.remove_sync_error_flag_on_report(uuid)
        super().delete(*args, **kwargs)


class Report(MapEntityMixin, PicturesMixin, TimeStampedModelMixin, NoDeleteMixin, AddPropertyMixin, ZoningPropertiesMixin):
    """User reports, submitted via *Geotrek-rando* or parsed from Suricate API."""

    email = models.EmailField(verbose_name=_("Email"))
    comment = models.TextField(blank=True, default="", verbose_name=_("Comment"))
    activity = models.ForeignKey(
        "ReportActivity",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Activity"),
    )
    category = models.ForeignKey(
        "ReportCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Category"),
    )
    problem_magnitude = models.ForeignKey(
        "ReportProblemMagnitude",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_("Problem magnitude"),
    )
    status = models.ForeignKey(
        "ReportStatus",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=status_default,
        verbose_name=_("Status"),
    )
    geom = models.PointField(
        null=True,
        blank=True,
        default=None,
        verbose_name=_("Location"),
        srid=settings.SRID,
    )
    related_trek = models.ForeignKey(
        Trek,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_("Related trek"),
    )
    created_in_suricate = models.DateTimeField(
        blank=True, null=True,
        verbose_name=_("Creation date in Suricate")
    )
    external_uuid = models.UUIDField(
        editable=False, unique=True, null=True, verbose_name=_("Identifier")
    )
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    eid = models.CharField(blank=True, max_length=1024, default="", verbose_name=_('External id'))
    locked = models.BooleanField(default=False, verbose_name=_("Locked"))
    origin = models.CharField(
        blank=True, null=True, default="unknown", max_length=100, verbose_name=_("Origin")
    )
    last_updated_in_suricate = models.DateTimeField(
        blank=True, null=True,
        verbose_name=_("Last updated in Suricate")
    )
    assigned_user = models.ForeignKey(
        SelectableUser,
        blank=True,
        on_delete=models.PROTECT,
        null=True,
        verbose_name=_("Supervisor"),
        related_name="reports"
    )
    uses_timers = models.BooleanField(verbose_name=_("Use timers"), default=False, help_text=_("Launch timers to alert supervisor if report is not being treated on time"))
    sync_errors = models.IntegerField(verbose_name=_("Synchronisation error"), default=0, help_text=_("Synchronisation with Suricate is currently pending due to connection problems"))
    mail_errors = models.IntegerField(verbose_name=_("Mail error"), default=0, help_text=_("A notification email could not be sent. Please contact an administrator"))

    class Meta:
        verbose_name = _("Report")
        verbose_name_plural = _("Reports")
        ordering = ["-date_insert"]

    def __str__(self):
        """
        Also called 'tag' in views/serializers
        """
        if (settings.SURICATE_WORKFLOW_ENABLED or settings.SURICATE_MANAGEMENT_ENABLED) and self.eid:
            return f"{_('Report')} {self.eid}"
        else:
            return f"{_('Report')} {self.pk}"

    @property
    def tag_verbose_name(self):
        return _("Tag")

    @classmethod
    def get_suricate_messenger(cls):
        return SuricateMessenger(PendingSuricateAPIRequest)

    @property
    def full_url(self):
        try:
            return "{}{}".format(settings.ALLOWED_HOSTS[0], self.get_detail_url())
        except KeyError:
            # Do not display url if there is no ALLOWED_HOSTS
            return ""

    @classmethod
    def get_create_label(cls):
        return _("Add a new feedback")

    @property
    def geom_wgs84(self):
        return self.geom.transform(4326, clone=True)

    @property
    def color(self):
        default = settings.MAPENTITY_CONFIG.get('MAP_STYLES', {}).get("detail", {}).get("color", "#ffff00")
        if not(settings.ENABLE_REPORT_COLORS_PER_STATUS) or self.status is None or self.status.color is None:
            return default
        else:
            return self.status.color

    @property
    def comment_text(self):
        return html.unescape(self.comment)

    def send_report_to_managers(self, template_name="feedback/report_email.txt"):
        subject = _("Feedback from {email}").format(email=self.email)
        message = render_to_string(template_name, {"report": self})
        mail_managers(subject, message, fail_silently=False)

    def try_send_report_to_managers(self):
        try:
            self.send_report_to_managers()
        except Exception as e:
            logger.error("Email could not be sent to managers.")
            logger.exception(e)  # This sends an email to admins :)

    def save_no_suricate(self, *args, **kwargs):
        """Save method for No Suricate mode"""
        if not self.pk:  # New report should alert
            self.try_send_report_to_managers()
        super().save(*args, **kwargs)  # Report updates should do nothing more

    def save_suricate_report_mode(self, *args, **kwargs):
        """Save method for Suricate Report mode"""
        if not self.pk:  # New report should alert managers AND be sent to Suricate
            self.try_send_report_to_managers()
            self.get_suricate_messenger().post_report(self)
        super().save(*args, **kwargs)  # Report updates should do nothing more

    def save_suricate_management_mode(self, *args, **kwargs):
        """Save method for Suricate Management mode"""
        if not self.pk:  # This is a new report
            if self.external_uuid is None:  # This new report comes from Rando or Admin : let Suricate handle it first, don't even save it
                self.get_suricate_messenger().post_report(self)
            else:  # This new report comes from Suricate : save
                super().save(*args, **kwargs)
        else:  # Report updates should do nothing more
            super().save(*args, **kwargs)

    def save_suricate_workflow_mode(self, *args, **kwargs):
        """Save method for Suricate Management mode"""
        if not self.pk:  # This is a new report
            if self.external_uuid is None:  # This new report comes from Rando or Admin : let Suricate handle it first, don't even save it
                self.get_suricate_messenger().post_report(self)
            else:  # This new report comes from Suricate : assign workflow manager if needed and save
                if self.status.identifier in ['filed']:
                    self.assigned_user = WorkflowManager.objects.first().user
                super().save(*args, **kwargs)
        else:  # Report updates should do nothing more
            super().save(*args, **kwargs)

    def attach_email(self, message, to):
        date = timezone.now()
        author = f"{settings.DEFAULT_FROM_EMAIL} {_('to')} {to}"
        content = message
        type = _("Follow-up message generated by Geotrek")
        # Create message object
        AttachedMessage.objects.create(
            date=date,
            report=self,
            author=author,
            content=content,
            type=type
        )

    def try_send_email(self, subject, message):
        try:
            success = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.assigned_user.email], fail_silently=False)
        except Exception as e:
            success = 0  # 0 mails successfully sent
            logger.error("Email could not be sent to report's assigned user.")
            logger.exception(e)  # This sends an email to admins :)
            # Save failed email to database
            PendingEmail.objects.create(
                recipient=self.assigned_user.email,
                subject=subject,
                message=message,
                error_message=e.args,
                report=self
            )
        finally:
            if success == 1:
                self.attach_email(message, self.assigned_user.email)

    @property
    def formatted_external_uuid(self):
        """
        Formatted UUIDs as they are found in Suricate
        stored:   13D3CBEF-ED65-1184-53DC-47EBCC7BE0FD
        expected: 13D3CBEF-ED65-1184-53DC47EBCC7BE0FD
        """
        uuid = str(self.external_uuid).upper()
        formatted_external_uuid = "".join(str(uuid).rsplit("-", 1))
        return formatted_external_uuid

    def notify_assigned_user(self, message):
        subject = _("Geotrek - New report to process")
        message = render_to_string("feedback/affectation_email.txt", {"report": self, "message": message})
        self.try_send_email(subject, message)

    def notify_late_report(self, status_id):
        subject = _("Geotrek - Late report processsing")
        message = render_to_string(f"feedback/late_{status_id}_email.txt", {"report": self})
        self.try_send_email(subject, message)

    def lock_in_suricate(self):
        self.get_suricate_messenger().lock_alert(self.formatted_external_uuid)

    def unlock_in_suricate(self):
        self.get_suricate_messenger().unlock_alert(self.formatted_external_uuid)

    def change_position_in_suricate(self, force=False):
        rep_gps = self.geom.transform(4326, clone=True)
        long, lat = rep_gps
        self.get_suricate_messenger().update_gps(self.formatted_external_uuid, lat, long, force)

    def update_status_in_suricate(self, status_identifier, message):
        self.get_suricate_messenger().update_status(self.formatted_external_uuid, status_identifier, message)

    def send_notifications_on_status_change(self, old_status_identifier, message):
        if old_status_identifier in NOTIFY_SURICATE_AND_SENTINEL and (self.status.identifier in NOTIFY_SURICATE_AND_SENTINEL[old_status_identifier]):
            self.update_status_in_suricate(self.status.identifier, message)
            if message:
                self.get_suricate_messenger().message_sentinel(self.formatted_external_uuid, message)

    def save(self, *args, **kwargs):
        if not settings.SURICATE_REPORT_ENABLED and not settings.SURICATE_MANAGEMENT_ENABLED and not settings.SURICATE_WORKFLOW_ENABLED:
            self.save_no_suricate(*args, **kwargs)  # No Suricate Mode
        elif settings.SURICATE_REPORT_ENABLED and not settings.SURICATE_MANAGEMENT_ENABLED and not settings.SURICATE_WORKFLOW_ENABLED:
            self.save_suricate_report_mode(*args, **kwargs)  # Suricate Report Mode
        elif settings.SURICATE_MANAGEMENT_ENABLED and not settings.SURICATE_WORKFLOW_ENABLED:
            self.save_suricate_management_mode(*args, **kwargs)  # Suricate Management Mode
        elif settings.SURICATE_WORKFLOW_ENABLED:
            self.save_suricate_workflow_mode(*args, **kwargs)  # Suricate Workflow Mode

    @property
    def created_in_suricate_display(self):
        return date_format(self.created_in_suricate, "SHORT_DATETIME_FORMAT")

    @property
    def last_updated_in_suricate_display(self):
        return date_format(self.last_updated_in_suricate, "SHORT_DATETIME_FORMAT")

    @property
    def name_display(self):
        """
        Displayed on linked interventions' pages
        """
        s = '<a data-pk="%s" href="%s" title="%s">%s</a>' % (self.pk,
                                                             self.get_detail_url(),
                                                             str(self),
                                                             str(self))
        return s

    @property
    def eid_verbose_name(self):
        return _("Label")

    def distance(self, to_cls):
        """Distance to associate this report to another class"""
        return settings.REPORT_INTERSECTION_MARGIN

    def report_interventions(self):
        if 'geotrek.maintenance' in settings.INSTALLED_APPS:
            report_content_type = ContentType.objects.get_for_model(Report)
            filters = Q(target_type=report_content_type, target_id=self.id)
            return Intervention.objects.existing().filter(filters).distinct('pk')
        return None

    @classmethod
    def latest_updated_by_status(cls, status_id):
        reports = cls.objects.existing().filter(status__identifier=status_id)
        if reports:
            return reports.latest('date_update').get_date_update()
        return cls.objects.none()


Report.add_property('paths', lambda self: intersecting(Path, self), _("Paths"))
Report.add_property('treks', lambda self: intersecting(Trek, self), _("Treks"))
Report.add_property('pois', lambda self: intersecting(POI, self), _("POIs"))
Report.add_property('services', lambda self: intersecting(Service, self), _("Services"))
if 'geotrek.maintenance' in settings.INSTALLED_APPS:
    Report.add_property('interventions', lambda self: Report.report_interventions(self), _("Interventions"))


class ReportActivity(models.Model):
    """Activity involved in report"""

    label = models.CharField(verbose_name=_("Activity"), max_length=128)
    identifier = models.PositiveIntegerField(
        verbose_name=_("Suricate id"), null=True, blank=True, unique=True
    )

    class Meta:
        verbose_name = _("Activity")
        verbose_name_plural = _("Activities")
        ordering = ("label",)

    def __str__(self):
        return self.label


class ReportCategory(models.Model):
    label = models.CharField(verbose_name=_("Category"), max_length=128)
    identifier = models.PositiveIntegerField(_("Suricate id"), null=True, blank=True)

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ("label",)

    def __str__(self):
        return self.label


class ReportStatus(models.Model):
    label = models.CharField(verbose_name=_("Status"), max_length=128)
    identifier = models.CharField(
        null=True,
        blank=True,
        unique=True,
        max_length=100,
        verbose_name=_("Identifiant"),
    )
    color = ColorField(verbose_name=_("Color"), default='#444444')

    class Meta:
        verbose_name = _("Status")
        verbose_name_plural = _("Status")

    def __str__(self):
        return self.label


class ReportProblemMagnitude(models.Model):
    """Report problem magnitude"""

    label = models.CharField(verbose_name=_("Problem magnitude"), max_length=128)
    identifier = models.PositiveIntegerField(
        verbose_name=_("Suricate id"), null=True, blank=True, unique=True
    )
    suricate_label = models.CharField(
        verbose_name=_("Suricate label"),
        max_length=128,
        null=True, blank=True, unique=True
    )

    class Meta:
        verbose_name = _("Problem magnitude")
        verbose_name_plural = _("Problem magnitudes")
        ordering = ("id",)

    def __str__(self):
        return self.label


class AttachedMessage(models.Model):
    """Messages are attached to a report"""

    date = models.DateTimeField()
    author = models.CharField(max_length=300)
    content = models.TextField()
    identifier = models.IntegerField(
        null=True, blank=True, verbose_name=_("Identifiant")
    )
    type = models.CharField(max_length=100)
    report = models.ForeignKey(Report, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('identifier', 'date', 'report')


class TimerEvent(models.Model):
    """
    This model stores notification dates for late reports, according to management workflow
    Run 'check_timers" command everyday to send notifications and clear timers
    """

    step = models.ForeignKey(ReportStatus, on_delete=models.CASCADE, null=False, related_name="timers")
    report = models.ForeignKey(Report, on_delete=models.CASCADE, null=False, related_name="timers")
    date_event = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField()
    notification_sent = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.report.uses_timers:
            if not self.pk:
                days_nb = settings.SURICATE_WORKFLOW_SETTINGS.get(f"TIMER_FOR_{self.step.identifier.upper()}_REPORTS_IN_DAYS", 30)
                self.deadline = self.date_event + timedelta(days=days_nb)
            super().save(*args, **kwargs)
        # Don't save if report doesn't use timers

    def is_linked_report_late(self):
        # Deadline is over and report status still hasn't changed
        return (timezone.now() > self.deadline) and (self.report.status.identifier == self.step.identifier)

    def notify_if_needed(self):
        if not(self.notification_sent) and self.is_linked_report_late():
            self.report.notify_late_report(self.step.identifier)
            late_status = ReportStatus.objects.get(identifier=STATUS_WHEN_REPORT_IS_LATE[self.step.identifier])
            self.report.status = late_status
            self.report.save()
            self.notification_sent = True
            self.save()

    def is_obsolete(self):
        obsolete_notified = (timezone.now() > self.deadline) and self.notification_sent  # Notification sent by timer
        obsolete_unused = self.report.status.identifier != self.step.identifier  # Report status changed, therefore it was dealt with in time
        return obsolete_notified or obsolete_unused


class PendingEmail(models.Model):
    recipient = models.EmailField(verbose_name=_("Email"), max_length=256, blank=True, null=True)
    subject = models.CharField(max_length=200, null=False, blank=False)
    message = models.TextField(verbose_name=_("Message"), blank=False, null=False)
    error_message = models.TextField(null=False, blank=False)
    retries = models.IntegerField(blank=False, default=0)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, null=True)

    def retry(self):
        try:
            success = send_mail(self.subject, self.message, settings.DEFAULT_FROM_EMAIL, [self.recipient], fail_silently=False)
            self.delete()
        except Exception as e:
            success = 0  # 0 mails successfully sent
            self.retries += 1
            self.error_message = str(e.args)  # Keep last exception message
            self.save()
        finally:
            if success == 1 and self.report:
                self.report.attach_email(self.message, self.recipient)

    def save(self, *args, **kwargs):
        # Set mail_error flag on report
        report = self.report
        if report and not self.pk:
            report.mail_errors = F('mail_errors') + 1
            report.save()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Remove mail_error flag from report
        report = self.report
        if report:
            report.mail_errors = F('mail_errors') - 1
            report.save()
        super().delete(*args, **kwargs)


class WorkflowManager(models.Model):
    """
    Workflow Manager is a User that is responsible for assigning reports to other Users and confirming that reports can be marked as resolved
    There should be only one Workflow Manager, who will receive notification emails when an action is needed
    """
    user = models.ForeignKey(SelectableUser, on_delete=models.PROTECT)

    class Meta:
        verbose_name = _("Workflow Manager")
        verbose_name_plural = _("Workflow Managers")

    def __str__(self):
        return f"{self.user.username} ({self.user.email})"

    def attach_email_to_report(self, report, message, to):
        date = timezone.now()
        author = f"{settings.DEFAULT_FROM_EMAIL} {_('to')} {to}"
        content = message
        type = _("Follow-up message generated by Geotrek")
        # Create message object
        AttachedMessage.objects.create(
            date=date,
            report=report,
            author=author,
            content=content,
            type=type
        )

    def try_send_email(self, subject, message, report=None):
        try:
            success = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.user.email], fail_silently=False)
        except Exception as e:
            success = 0  # 0 mails successfully sent
            logger.error("Email could not be sent to Workflow Managers.")
            logger.exception(e)  # This sends an email to admins :)
            # Save failed email to database
            PendingEmail.objects.create(
                recipient=self.user.email,
                subject=subject,
                message=message,
                error_message=e.args
            )
        finally:
            if success == 1 and report:
                self.attach_email_to_report(report, message, self.user.email)

    def notify_report_to_solve(self, report):
        subject = _("Geotrek - A report must be solved")
        message = render_to_string("feedback/cloture_email.txt", {"report": report})
        self.try_send_email(subject, message, report)

    def notify_new_reports(self, reports):
        reports_urls = []
        for report in Report.objects.filter(pk__in=reports):
            reports_urls.append(report.full_url)
        subject = _("Geotrek - New reports from Suricate")
        message = render_to_string("feedback/reports_email.txt", {"reports_urls": reports_urls})
        self.try_send_email(subject, message)


class PredefinedEmail(models.Model):
    """
    An email with predefined content to be sent through Suricate Workflow
    """
    label = models.CharField(blank=False, max_length=500, verbose_name=_('Predefined email'))
    text = models.TextField(blank=True, help_text='Mail body', verbose_name=_('Content'))

    class Meta:
        verbose_name = _("Predefined email")
        verbose_name_plural = _("Predefined emails")

    def __str__(self):
        return self.label


class WorkflowDistrict(models.Model):
    """
    Workflow Manager is a User that is responsible for assigning reports to other Users and confirming that reports can be marked as resolved
    There should be only one Workflow Manager, who will receive notification emails when an action is needed
    """
    district = models.ForeignKey(District, on_delete=models.PROTECT)

    class Meta:
        verbose_name = _("Workflow District")
        verbose_name_plural = _("Workflow Districts")

    def __str__(self):
        return str(self.district)
