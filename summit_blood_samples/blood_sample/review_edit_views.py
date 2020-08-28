from datetime import datetime
import datetime
import time
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View
from django.utils.timezone import make_aware

from manage_users.models import *
import dateutil.relativedelta
from .models import *

# Get an instance of a logger
logger = logging.getLogger(__name__)

class EditBloodSampleView(LoginRequiredMixin, View):
    """
    Class for Editing blood samples
    """
    blood_sample_review_template = \
        'review_blood_sample/blood-sample-edit.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get blood sample object
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.blood_sample_review_template, {
            "object": BloodSample.objects.get(id=int(request.GET.get('id'))),
            "STATECHOICE": dict(STATECHOICE)
        })

    def post(self, request, *args, **kwargs):
        bs_object = BloodSample.objects.get(id=int(request.GET.get('id')))

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in ['Comments', 'Barcode', 'State']}

        data_object = bs_object.__dict__

        # Filter editable data from original blood sample object
        data_object = {key: data_object[key]
                       for key in ['Comments', 'Barcode', 'State']}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the blood sample object and storing the info about
        # changes in BloodSampleChanges
        try:
            for i in diffs:
                setattr(bs_object, i[0], i[1][1])
                BloodSampleChanges.objects.create(
                    Field=i[0],
                    FromValue=i[1][0],
                    ChangedBy=request.user,
                )
        except Exception as e:
                logger.error(f'Something went wrong in creating Blood Sample \
                    changes data - {e}')
                return None

        try:
            bs_object.save()
        except Exception as e:
                logger.error(f'Something went wrong in updating Blood Sample \
                    details - {e}')
                return None

        return JsonResponse({
            'status': 200,
            'message': f'{request.GET.get("id")} sample updated successfully'
        })


class EditProcessedBsView(LoginRequiredMixin, View):
    """
    Class for editing Blood sample data in processed matched
    records review table
    """

    blood_sample_review_template = 'review_processed/processed-bs-edit.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the Blood sample and processed record data
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.blood_sample_review_template, {
            "object": BloodSample.objects.get(id=int(request.GET.get('id'))),
            "processed_object": \
                ProcessedReport.objects.get(id=\
                    int(request.GET.get('processed_id'))),
            "STATECHOICE": dict(STATECHOICE)
        })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Blood sample data
        :param request: request object
        :return: HttpResponse object
        """
        bs_object = BloodSample.objects.get(id=int(request.GET.get('id')))

        editable_fields = ['Comments', 'State']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_object = bs_object.__dict__

        # Filter editable data from original blood sample object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the blood sample object and storing the info about
        # changes in BloodSampleChanges
        try:
            for i in diffs:
                setattr(bs_object, i[0], i[1][1])
                BloodSampleChanges.objects.create(
                    Field=i[0],
                    FromValue=i[1][0],
                    ChangedBy=request.user,
                )
        except Exception as e:
                logger.error(f'Something went wrong in creating Blood Sample \
                    changes data - {e}')
                return None
        try:
            bs_object.save()
        except Exception as e:
                logger.error(f'Something went wrong in updating Blood Sample \
                    details - {e}')
                return None

        return JsonResponse({
            'status': 200,
            'message': f'{request.GET.get("id")} sample updated successfully'
        })


class EditManifestView(LoginRequiredMixin, View):
    """
    Class for editing Manifest records
    """
    manifest_edit_template = 'review_manifest/manifest-edit.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the Manifest record data
        :param request: request object
        :return: HttpResponse object
        """
        Rooms = ManifestRecords.objects.all().values_list(
            'Room', flat=True).distinct()[::1]
        return render(request, self.manifest_edit_template, {
            "object": ManifestRecords.objects.get(id=\
                int(request.GET.get('id'))),
            "rooms": sorted(Rooms, key=lambda L: (L.lower(), L)),
        })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Manifest data
        :param request: request object
        :return: HttpResponse object
        """
        mf_object = ManifestRecords.objects.get(id=\
            int(request.GET.get('id')))

        editable_fields = ['CohortId', 'Barcode',
                           'Room', 'Visit', 'Site', 'Comments']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_object = mf_object.__dict__

        # Filter editable data from original mainfest object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the manifest object and storing the info about changes
        # in ManifestChanges
        try:
            for i in diffs:
                setattr(mf_object, i[0], i[1][1])
                ManifestChanges.objects.create(
                    Field=i[0],
                    FromValue=i[1][0],
                    ChangedBy=request.user,
                )
        except Exception as e:
                logger.error(f'Something went wrong in creating Manifest \
                    changes data - {e}')
                return None

        try:
            mf_object.save()
        except Exception as e:
                logger.error(f'Something went wrong in updating Manifest \
                    details - {e}')
                return None

        return JsonResponse({
            'status': 200,
            'message': f'{request.GET.get("id")} \
                manifest updated successfully'})


class EditReceiptView(LoginRequiredMixin, View):
    """
    Class for editing Receipt records
    """
    receipt_edit_template = 'review_receipt/receipt-edit.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the Receipt record data
        :param request: request object
        :return: HttpResponse object
        """
        if request.GET.get('manifest', 'False') == 'True':
            return render(request, self.receipt_edit_template, {
                "object": ReceiptRecords.objects.get(id=\
                    int(request.GET.get('id'))),
                "manifest_object": ManifestRecords.objects.get(id=\
                    int(request.GET.get('manifestid'))),
            })
        else:
            return render(request, self.receipt_edit_template, {
                "object": ReceiptRecords.objects.get(id=\
                    int(request.GET.get('id'))),
                "manifest_object": None
            })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Receipt data
        :param request: request object
        :return: HttpResponse object
        """
        rr_object = ReceiptRecords.objects.get(id=int(request.GET.get('id')))

        editable_fields = ['Barcode', 'DateTimeTaken', 'Comments']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_edit['DateTimeTaken'] = \
            make_aware(datetime.datetime.strptime(\
                data_edit['DateTimeTaken'], "%Y-%m-%dT%H:%M"))

        data_object = rr_object.__dict__

        # Filter editable data from original receipt object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the receipt object and storing the info about changes
        # in ReceiptChanges
        try:
            for i in diffs:
                setattr(rr_object, i[0], i[1][1])
                ReceiptChanges.objects.create(
                    Field=i[0],
                    FromValue=i[1][0],
                    ChangedBy=request.user,
                )
        except Exception as e:
                logger.error(f'Something went wrong in creating Receipt \
                    changes data - {e}')
                return None

        try:
            rr_object.save()
        except Exception as e:
                logger.error(f'Something went wrong in updating Receipt \
                    details - {e}')
                return None

        return JsonResponse({
            'status': 200,
            'message': f'{request.GET.get("id")} \
                receipt updated successfully'})


class EditProcessedView(LoginRequiredMixin, View):
    """
    Class for editing Processed records
    """
    processed_edit_template = 'review_processed/processed-edit.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the Processed record data
        :param request: request object
        :return: HttpResponse object
        """

        return render(request, self.processed_edit_template, {
            "object": ProcessedReport.objects.get(\
                id=int(request.GET.get('id'))),
        })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Processed data
        :param request: request object
        :return: HttpResponse object
        """
        pr_object = ProcessedReport.objects.get(id=\
            int(request.GET.get('id')))

        editable_fields = ['ParentId', 'Comments']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_object = pr_object.__dict__

        # Filter editable data from original processed object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the processed object and storing the info about
        # changes in ProcessedReportChanges
        try:
            for i in diffs:
                setattr(pr_object, i[0], i[1][1])
                ProcessedReportChanges.objects.create(
                    Field=i[0],
                    FromValue=i[1][0],
                    ChangedBy=request.user,
                )
        except Exception as e:
                logger.error(f'Something went wrong in creating Processed \
                    changes data - {e}')
                return None

        try:
            pr_object.save()
        except Exception as e:
                logger.error(f'Something went wrong in updating Processed \
                    details - {e}')
                return None

        return JsonResponse({
            'status': 200,
            'message': f'{request.GET.get("id")} \
                processed report updated successfully'})


class GetManifestFiltersView(LoginRequiredMixin, View):
    """
    Class for getting Manifest filters in review
    """

    def get(self, request, *args, **kwargs):
        """
        Method to get Manifest filters in review
        :param request: request object
        :return: HttpResponse object
        """
        Rooms = ManifestRecords.objects.all().values_list(
            'Room', flat=True).distinct()[::1]
        return JsonResponse({
            'status': 200,
            'rooms': sorted(Rooms, key=lambda L: (L.lower(), L)),
        })
