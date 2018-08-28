import threading

from django.db import connection
from django.db import models
from djangae.test import TestCase
from google.appengine.api import datastore

from djangae.contrib import sleuth


DEFAULT_NAMESPACE = connection.ops.connection.settings_dict.get("NAMESPACE")


class MetaQueryTestModel(models.Model):
    field1 = models.CharField(max_length=32)


class PrimaryKeyFilterTests(TestCase):

    def test_pk_in_with_slicing(self):
        i1 = MetaQueryTestModel.objects.create();

        self.assertFalse(
            MetaQueryTestModel.objects.filter(pk__in=[i1.pk])[9999:]
        )

        self.assertFalse(
            MetaQueryTestModel.objects.filter(pk__in=[i1.pk])[9999:10000]
        )

    def test_limit_correctly_applied_per_branch(self):
        MetaQueryTestModel.objects.create(field1="test")
        MetaQueryTestModel.objects.create(field1="test2")

        with sleuth.watch('google.appengine.api.datastore.Query.Run') as run_calls:

            list(MetaQueryTestModel.objects.filter(field1__in=["test", "test2"])[:1])

            self.assertEqual(1, run_calls.calls[0].kwargs['limit'])
            self.assertEqual(1, run_calls.calls[1].kwargs['limit'])

        with sleuth.watch('google.appengine.api.datastore.Query.Run') as run_calls:

            list(MetaQueryTestModel.objects.filter(field1__in=["test", "test2"])[1:2])

            self.assertEqual(2, run_calls.calls[0].kwargs['limit'])
            self.assertEqual(2, run_calls.calls[1].kwargs['limit'])


class ExcludeFilterTestCase(TestCase):

    def test_exclude_with_empty_db(self):
        queryset = MetaQueryTestModel.objects.exclude(field1="Lucy")
        self.assertEqual(len(queryset), 0)

    def test_exclude_without_empty_db(self):
        # Create anything in the DB to avoid it being empty
        entity = datastore.Entity(kind="whatever", namespace=DEFAULT_NAMESPACE)
        datastore.Put(entity)

        queryset = MetaQueryTestModel.objects.exclude(field1="Lucy")
        self.assertEqual(len(queryset), 0)

    def test_datastore_api_thread_safe(self):

        def func(filters):
            query = datastore.Query("my_kind", filters=filters)
            query_run_args = {'limit': None}
            [x for x in query.Run(**query_run_args)]

        thread1 = threading.Thread(target=func, args=({'field1 >': u'Lucy'},))
        thread2 = threading.Thread(target=func, args=({'field1 >': u'Lucy'},))
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

