from django.test import TestCase
from django.urls import reverse

from mapentity.factories import SuperUserFactory

from geotrek.authent.models import Structure
from .base import AuthentFixturesTest
from .. import factories


class AuthentAdminTest(TestCase):
    def setUp(self):
        self.admin = SuperUserFactory.create(password='booh')

    def login(self, user):
        success = self.client.login(username=user.username, password='booh')
        self.assertTrue(success)

    def test_cant_delete_last_structure(self):
        self.login(self.admin)
        delete_url = reverse('admin:authent_structure_delete', args=[Structure.objects.first().pk])
        response = self.client.post(delete_url, {'post': 'yes'})
        self.assertEqual(response.status_code, 403)

    def test_can_delete_structure(self):
        self.login(self.admin)
        factories.StructureFactory.create()
        delete_url = reverse('admin:authent_structure_delete', args=[Structure.objects.first().pk])
        response = self.client.post(delete_url, {'post': 'yes'})
        self.assertEqual(response.status_code, 403)


class AdminSiteTest(AuthentFixturesTest):
    def setUp(self):
        self.admin = SuperUserFactory.create(password='booh')
        self.pathmanager = factories.PathManagerFactory.create(password='booh')
        self.trekmanager = factories.TrekkingManagerFactory.create(password='booh')
        self.user = factories.UserFactory.create(password='booh')

    def tearDown(self):
        self.client.logout()
        self.admin.delete()
        self.pathmanager.delete()
        self.trekmanager.delete()
        self.user.delete()

    def login(self, user):
        success = self.client.login(username=user.username, password='booh')
        self.assertTrue(success)

    def test_user_cant_access(self):
        self.login(self.user)
        response = self.client.get('/admin/')
        self.assertRedirects(response, '/admin/login/?next=/admin/')

    def test_admin_can_see_everything(self):
        self.login(self.admin)
        response = self.client.get('/admin/core/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/admin/trekking/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/admin/')
        self.assertContains(response, 'Core')
        self.assertContains(response, 'Land')
        self.assertContains(response, 'Trekking')

    def test_path_manager_cannot_see_trekking_apps(self):
        self.login(self.pathmanager)
        response = self.client.get('/admin/core/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/admin/trekking/')
        self.assertEqual(response.status_code, 404)
        response = self.client.get('/admin/')
        self.assertContains(response, 'Core')
        self.assertContains(response, 'Maintenance')
        self.assertContains(response, 'Infrastructure')
        self.assertContains(response, 'Signage')
        self.assertContains(response, 'Land')
        self.assertNotContains(response, 'Zoning')
        self.assertNotContains(response, 'Trekking')

    def test_trek_manager_cannot_see_core_apps(self):
        self.login(self.trekmanager)
        response = self.client.get('/admin/core/')
        self.assertEqual(response.status_code, 404)
        response = self.client.get('/admin/trekking/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/admin/')
        self.assertContains(response, 'Trekking')
        self.assertNotContains(response, 'Core')
        self.assertNotContains(response, 'Maintenance')
        self.assertNotContains(response, 'Infrastructure')
        self.assertNotContains(response, 'Signage')
        self.assertNotContains(response, 'Zoning')
        self.assertNotContains(response, 'Land')
