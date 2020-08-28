import math
from datetime import datetime
import datetime
import time
import pandas as pd

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View

from manage_users.models import *
import dateutil.relativedelta
from .models import *

from .upload_views import *

from .choices_data import \
    state_status, \
    site_choices, \
    visit_choices, \
    site_held_choices


class ReviewView(LoginRequiredMixin, View):
    """
    Class for reviewing all the uploaded files with day navigation
    """

    blood_sample_review_template = \
        'review_blood_sample/blood-sample-review.html'
    blood_sample_review_table_template = \
        'review_blood_sample/blood-sample-table.html'
    manifest_review_template = 'review_manifest/manifest-review.html'
    manifest_review_table_template = 'review_manifest/manifest-table.html'
    receipt_review_template = 'review_receipt/receipt-review.html'
    receipt_review_table_template = 'review_receipt/receipt-table.html'
    processed_review_template = 'review_processed/processed-review.html'
    processed_review_table_template = 'review_processed/processed-table.html'

    def get(self, request, *args, **kwargs):
        """
        Method to upload the Processed
        :param request: request object with review type and day
        :return: HttpResponse object
        """
        review_type = request.GET.get("type", "blood_sample")
        page = int(request.GET.get('page', 1))
        table = request.GET.get('table', 'False')
        day, days = UploadView.get_dayformated_and_days(self, request)

        if review_type == "blood_sample":
            # Getting imported sample files in given day
            blood_samples_imported = BloodSampleImport.objects.filter(
                CreatedAt__range=\
                    (day.replace(hour=0, minute=0, second=0, microsecond=0), \
                      day.replace(
                    hour=23, minute=59, second=59, microsecond=0)))

            # Checking latest uploaded sample file is reviewed or not
            if blood_samples_imported.count() > 0:
                sample_import_latest = blood_samples_imported.last()
                # If not reviewed changing the Reviewed column to True
                if not sample_import_latest.Reviewed:
                    sample_import_latest.Reviewed = True
                    sample_import_latest.save()

            # When first opening the review popup updating the day to the
            # latest day where records are available.
            # This will avoid user to unnecessary navigation to the day
            # where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and \
                BloodSample.objects.count():
                day = BloodSample.objects.all().order_by('-CreatedAt')\
                    .first().CreatedAt
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()

            # Getting the BloodSample records
            query_results = BloodSample.objects.filter(
                CreatedAt__range=(day.replace(hour=0, minute=0, second=0, \
                     microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0)))\
                        .order_by('CreatedAt', 'CohortId', 'Barcode')

            # Getting results based on pagination
            paginator = Paginator(query_results, settings.ITEMS_PER_PAGE)

            if table == "True":
                try:
                    results = paginator.page(page)
                except PageNotAnInteger:
                    results = paginator.page(1)
                except EmptyPage:
                    results = paginator.page(paginator.num_pages)
                return render(request,
                              self.blood_sample_review_table_template, {
                    "objects": results.object_list,
                    "current_page": page,
                    "class": 'reviewBloodDay',
                    "total_pages": paginator.num_pages
                })

            # Disabling the feature dates
            shownextday = datetime.datetime.today().strftime(
                '%d%b%y') in [i.strftime('%d%b%y') for i in days]

            return render(request, self.blood_sample_review_template, {
                "current_page": page,
                "total_pages": paginator.num_pages,
                "days": days,
                "active": day,
                "shownextday": shownextday,
                "class": 'reviewBloodDay',
            })

        if review_type == "manifest":
            # When first opening the review popup updating the day to
            # the latest day where records are there.
            # This will avoid user to unnecessary navigation to the day
            # where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and \
                ManifestRecords.objects.count():
                day = ManifestRecords.objects.all().order_by(
                    '-CollectionDateTime').first().CollectionDateTime
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()

            # Preparing raw sql query with filters
            qry = ""

            if request.GET.get('Site', ''):
                qry += f" AND mr.\"Site\" = '{request.GET.get('Site')}'"
            if request.GET.get('Visit', ''):
                qry += f" AND mr.\"Visit\" = '{request.GET.get('Visit')}'"
            if request.GET.get('Room', ''):
                qry += f" AND mr.\"Room\" = '{request.GET.get('Room')}'"

            query = '''
                SELECT
                    "mr"."id",
                    "bs"."CohortId",
                    "bs"."Barcode" as "BloodSampleBarcode",
                    "bs"."AppointmentId",
                    "bs"."SiteNurseEmail",
                    "bs"."Comments",
                    "bs"."CreatedAt",
                    "bs"."State",
                    "mr"."CohortId" as "ManifestCohortId",
                    "mr"."Barcode" as "ManifestBarcode",
                    "mr"."Visit",
                    "mr"."Site",
                    "mr"."Room",
                    "mr"."Comments" as "ManifestComments",
                    "mr"."CollectionDateTime"
                FROM blood_sample_manifestrecords as mr
                INNER JOIN blood_sample_bloodsample as bs ON \
                    ( mr."CohortId" = bs."CohortId")
                WHERE mr."CollectionDateTime" BETWEEN '{}' AND '{}'{}
                order by bs."CohortId";
                '''.format(day.replace(hour=0, minute=0, second=0, \
                    microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), \
                           day.replace(hour=23, minute=59, second=59, \
                               microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), \
                                    qry)

            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                data = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

            items_per_page = settings.ITEMS_PER_PAGE
            total_pages = math.ceil(len(data) / items_per_page)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': 1 if total_pages == 0 else total_pages,
                    'current_page': 1 if page == 0 else page, })

            if table == "True":
                # records based on page to display
                record_start = (page - 1) * items_per_page
                record_end = page * items_per_page
                data = data[record_start:record_end]

                # Converting State, Visit and Site choices to field names
                for row in range(len(data)):
                    data[row]['State'] = state_status[data[row]['State']]
                    data[row]['Visit'] = visit_choices[data[row]['Visit']]
                    data[row]['Site'] = site_choices[data[row]['Site']]

                return render(request, self.manifest_review_table_template, {
                    "objects": data,
                    "current_page": 1 if page == 0 else page,
                    "total_pages": 1 if total_pages == 0 else total_pages,
                    "class": 'reviewManifestDay',
                })

            # Disabling the feature dates
            shownextday = datetime.datetime.today().strftime(
                '%d%b%y') in [i.strftime('%d%b%y') for i in days]

            # Getting Pagination count for Unmatched tables
            # Comparing Blood Sample with Manifest
            query = '''
                SELECT count(1)
                FROM blood_sample_bloodsample as bs
                left join blood_sample_manifestrecords as mr on \
                    bs."CohortId" = mr."CohortId"
                WHERE mr."id" is null AND bs."CreatedAt" BETWEEN '{}' AND '{}'
            '''.format(
                day.replace(hour=0, minute=0, second=0, microsecond=0), \
                    day.replace(
                    hour=23, minute=59, second=59, microsecond=0))
            with connection.cursor() as cursor:
                cursor.execute(query)
                data_count = cursor.fetchall()[0][0]
                bs_unmatched_total_pages = math.ceil(
                    data_count / settings.ITEMS_PER_PAGE)

            # Comparing Manifest with Blood Sample

            query = '''
                SELECT count(1)
                FROM blood_sample_manifestrecords as mr
                left join blood_sample_bloodsample as bs on \
                    bs."CohortId" = mr."CohortId"
                WHERE mr."id" is null AND mr."CollectionDateTime" \
                    BETWEEN '{}' AND '{}'
            '''.format(
                day.replace(hour=0, minute=0, second=0, microsecond=0), \
                     day.replace(
                    hour=23, minute=59, second=59, microsecond=0))
            with connection.cursor() as cursor:
                cursor.execute(query)
                data_count = cursor.fetchall()[0][0]
                mf_unmatched_total_pages = math.ceil(
                    data_count / settings.ITEMS_PER_PAGE)

            return render(request, self.manifest_review_template, {
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                "bs_total_pages": 1 if bs_unmatched_total_pages == 0 \
                    else bs_unmatched_total_pages,
                "mf_total_pages": 1 if mf_unmatched_total_pages == 0 \
                    else mf_unmatched_total_pages,
                "days": days,
                "active": day,
                "shownextday": shownextday,
                "class": 'reviewManifestDay',
            })

        if review_type == "receipt":
            # When first opening the review popup updating the day to the
            # latest day where records are there.
            # This will avoid user to unnecessary navigation to the day
            # where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and \
                ReceiptRecords.objects.count():
                day = ReceiptRecords.objects.all().order_by(
                    '-DateTimeTaken').first().DateTimeTaken
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()

            # Preparing raw sql query with filters
            qry = ""

            if request.GET.get('Site', ''):
                qry += f" AND mr.\"Site\" = '{request.GET.get('Site')}'"
            if request.GET.get('Visit', ''):
                qry += f" AND mr.\"Visit\" = '{request.GET.get('Visit')}'"
            if request.GET.get('Room', ''):
                qry += f" AND mr.\"Room\" = '{request.GET.get('Room')}'"

            query = '''
                SELECT
                    bs."CohortId",
                    bs."AppointmentId",
                    bs."Barcode" as "BloodSampleBarcode",
                    bs."Comments",
                    bs."SiteNurseEmail",
                    bs."CreatedAt",
                    bs."State",
                    mr."id" as "ManifestId",
                    mr."Barcode" as "ManifestBarcode",
                    mr."CohortId" as "ManifestCohortId",
                    mr."Site",
                    mr."Visit",
                    mr."Room",
                    mr."CollectionDateTime",
                    mr."Comments" as "ManifestComments",
                    rr."id" as "ReceiptId",
                    rr."Barcode" as "ReceiptBarcode",
                    rr."Clinic",
                    rr."DateTimeTaken",
                    rr."TissueSubType",
                    rr."ReceivedDateTime",
                    rr."Volume",
                    rr."VolumeUnit",
                    rr."Comments" as "ReceiptComments"
                from blood_sample_receiptrecords as rr
                inner join blood_sample_manifestrecords as mr \
                    on (rr."Barcode"=mr."Barcode")
                inner join blood_sample_bloodsample as bs \
                    on (bs."CohortId"=mr."CohortId")
                WHERE rr."DateTimeTaken" BETWEEN '{}' AND '{}' {}
                order by bs."CohortId";
                '''.format(day.replace(hour=0, minute=0, second=0, \
                    microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                           day.replace(hour=23, minute=59, second=59, \
                               microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), \
                                    qry)

            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                data = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

            items_per_page = settings.ITEMS_PER_PAGE
            total_pages = math.ceil(len(data) / settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': 1 if total_pages == 0 else total_pages,
                    'current_page': 1 if page == 0 else page,
                })

            if table == "True":
                # records based on page to display
                record_start = (page - 1) * items_per_page
                record_end = page * items_per_page
                data = data[record_start:record_end]

                # Converting State, Visit and Site choices to field names
                for row in range(len(data)):
                    data[row]['State'] = state_status[data[row]['State']]
                    data[row]['Visit'] = visit_choices[data[row]['Visit']]
                    data[row]['Site'] = site_choices[data[row]['Site']]

                return render(request, self.receipt_review_table_template, {
                    "objects": data,
                    "current_page": 1 if page == 0 else page,
                    "total_pages": 1 if total_pages == 0 else total_pages,
                    "class": 'reviewReceiptDay',
                })

            # Disabling the feature dates
            shownextday = datetime.datetime.today().strftime(
                '%d%b%y') in [i.strftime('%d%b%y') for i in days]

            # Getting Pagination count for Unmatched tables
            # Comaring Blood sample and Manifest with Receipt
            data_bs = UnmachedReceiptView.get_umatched_bs_data(self, day, qry)
            bs_total_pages = math.ceil(len(data_bs) / settings.ITEMS_PER_PAGE)

            # Comaring Receipt with Blood sample and Manifest
            data_rr = UnmachedReceiptView.get_umatched_rr_data(self, day, "")
            rr_total_pages = math.ceil(len(data_rr) / settings.ITEMS_PER_PAGE)

            return render(request, self.receipt_review_template, {
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                "bsr_total_pages": 1 if bs_total_pages == 0 \
                    else bs_total_pages,
                "rr_total_pages": 1 if rr_total_pages == 0 \
                    else rr_total_pages,
                "days": days,
                "active": day,
                "shownextday": shownextday,
                "class": 'reviewReceiptDay',
            })

        if review_type == "processed":
            # When first opening the review popup updating the day to
            # the latest day where records are there.
            # This will avoid user to unnecessary navigation to
            # the day where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and \
                ProcessedReport.objects.count():
                day = ProcessedReport.objects.all().order_by(
                    '-ProcessedDateTime').first().ProcessedDateTime
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()

            # Getting settings options
            settings_options = dict(
                BS=[request.GET.get('BloodSample', \
                        "CohortId,Barcode,CreatedAt,Comments,State")],
                MR=[request.GET.get('Manifest', "Visit,Site,Room,Barcode")],
                RR=[request.GET.get('Receipt', "SampleId,Clinic")],
                PR=[request.GET.get('Processed', \
                    "ParentId,TissueSubType,ProcessedDateTime" + \
                    ",ReceivedDateTime,Volume,NumberOfChildren,Comments")])
            for table, columns in settings_options.items():
                for column in columns:
                    settings_options[table] = column.split(',')

            # Getting filters options
            filter_options = dict(
                DF=[""],
                DT=[""],
                Site=[request.GET.get('Site', '')],
                Room=[request.GET.get('Room', '')],
                Visit=[request.GET.get('Visit', '')],
                State=[request.GET.get('State', '')]
            )

            # finding the length of each table and assigning value to zero
            # if doesn't contain any selected columns from settings collection
            # length is required for colors in the display in download tab
            bs_len = len(settings_options['BS'])
            if bs_len == 1 and settings_options['BS'][0] == '':
                bs_len = 0

            mr_len = len(settings_options['MR'])
            if mr_len == 1 and settings_options['MR'][0] == '':
                mr_len = 0

            rr_len = len(settings_options['RR'])
            if rr_len == 1 and settings_options['RR'][0] == '':
                rr_len = 0

            pr_len = len(settings_options['PR'])
            if pr_len == 1 and settings_options['PR'][0] == '':
                pr_len = 0

            # generating a raw sql query based on filters and settings options
            # as requested by user
            query = """ SELECT """
            headers = []

            # selecting the required columns selected by the user
            for table, columns in settings_options.items():
                for column in columns:
                    if column != '':
                        # headers for columns in download tab that needs to be
                        # displayed
                        headers.append(column)
                    if table == 'BS' and column != '':
                        query += "bs.\"" + column + "\", "
                    if table == 'MR' and column != '':
                        query += "mr.\"" + column + "\", "
                    if table == 'RR' and column != '':
                        query += "rr.\"" + column + "\", "
                    if table == 'PR' and column != '':
                        query += "pr.\"" + column + "\", "

            query += "bs.\"id\" as \"BloodSampleId\", pr.\"id\" \
                 as \"ProcessedId\", "

            query = query[:-2]
            query += """from blood_sample_processedreport as pr
                        join blood_sample_receiptrecords as rr on \
                            pr."ParentId" = rr."SampleId"
                        join blood_sample_manifestrecords as mr on \
                            rr."Barcode" = mr."Barcode"
                        join blood_sample_bloodsample as bs on \
                            bs."CohortId" = mr."CohortId"
                    """
            extra = ' WHERE '

            # adding filtered values as requested by user
            for filt, value in filter_options.items():
                if filt == 'Site' and value[0] != '':
                    extra += "mr.\"Site\"='" + value[0] + "' AND "

                if filt == 'Room' and value[0] != '':
                    extra += "mr.\"Room\"='" + value[0] + "' AND "

                if filt == 'Visit' and value[0] != '':
                    extra += "mr.\"Visit\"='" + value[0] + "' AND "

                if filt == 'State' and value[0] != '':
                    val = list(state_status.keys())[
                        list(state_status.values()).index(value[0])]
                    extra += "bs.\"State\"='" + val + "' AND "

            extra += """ pr.\"ProcessedDateTime\" BETWEEN '{}' AND '{}' AND """\
                .format(day.replace(hour=0, minute=0, second=0, microsecond=0),
                                                                                       day.replace(hour=23, minute=59, second=59, microsecond=0))

            extra = extra[0:-4]
            if extra != ' WH':
                query += extra

            #  ordering the data based on ids and barcode
            query += ' order by bs.\"CohortId\", mr.\"Barcode\"'

            with connection.cursor() as cursor:
                cursor.execute(query)
                # Fetch rows using fetchall() method.
                data = cursor.fetchall()

            # updating the data of enum field with respective data
            if 'State' in settings_options['BS']:
                ind = headers.index('State')
                for row in range(len(data)):
                    data[row] = list(data[row])
                    data[row][ind] = state_status[data[row][ind]]
                    data[row] = tuple(data[row])

            if 'Site' in settings_options['MR']:
                ind = headers.index('Site')
                for row in range(len(data)):
                    if data[row][ind] is not None:
                        data[row] = list(data[row])
                        data[row][ind] = site_choices[data[row][ind]]
                        data[row] = tuple(data[row])

            if 'Visit' in settings_options['MR']:
                ind = headers.index('Visit')
                for row in range(len(data)):
                    if data[row][ind] is not None:
                        data[row] = list(data[row])
                        data[row][ind] = visit_choices[data[row][ind]]
                        data[row] = tuple(data[row])

            if 'SiteHeld' in settings_options['PR']:
                ind = headers.index('SiteHeld')
                for row in range(len(data)):
                    if data[row][ind] is not None:
                        data[row] = list(data[row])
                        data[row][ind] = site_held_choices[data[row][ind]]
                        data[row] = tuple(data[row])

            # display names of columns that display in download tab as headers
            row_headers = {
                'CohortId': 'Cohort id',
                'AppointmentId': 'Appointment id',
                'SiteNurseEmail': 'Site Nurse Email',
                'CreatedAt': 'Appointment date',
                'CollectionDateTime': 'Collection Date Time',
                'DateTimeTaken': 'Date Time Taken',
                'SampleId': 'Sample id',
                'TissueSubType': 'Tissue Sub Type',
                'ReceivedDateTime': 'Received Date Time',
                'VolumeUnit': 'Volume Unit',
                'ParentId': 'Parent id',
                'ProcessedDateTime': 'Processed Date Time',
                'NumberOfChildren': 'Number Of Children',
                'id': 'Id'
            }

            # updating the headers based on the column name
            for i in range(len(headers)):
                if headers[i] in row_headers:
                    headers[i] = row_headers[headers[i]]

            page = int(request.GET.get('page', 1))
            table = request.GET.get('table', 'False')

            total_pages = math.ceil(len(data) / settings.ITEMS_PER_PAGE)
            items_per_page = settings.ITEMS_PER_PAGE
            # records based on page to display
            record_start = (page - 1) * items_per_page
            record_end = page * items_per_page

            if len(data) != 0:
                headers.extend(['BloodSample Id', 'Processed Id'])
                data = [headers] + data[record_start:record_end]

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': 1 if total_pages == 0 else total_pages,
                    'current_page': 1 if page == 0 else page,
                })

            if table == "True":
                return render(request, self.processed_review_table_template, {
                    "objects": data,
                    "current_page": 1 if page == 0 else page,
                    "total_pages": 1 if total_pages == 0 else total_pages,
                    'db_data': data,
                    'bs_len': bs_len,
                    'mr_len': mr_len, 'rr_len': rr_len,
                    'pr_len': pr_len, 'settings': settings_options,
                    'filters': filter_options,
                    "class": 'reviewProcessedDay',
                })

            # Disabling the feature dates
            shownextday = datetime.datetime.today().strftime(
                '%d%b%y') in [i.strftime('%d%b%y') for i in days]

            qry = ""

            if request.GET.get('Site', ''):
                qry += f" AND mr.\"Site\" = '{request.GET.get('Site')}'"
            if request.GET.get('Visit', ''):
                qry += f" AND mr.\"Visit\" = '{request.GET.get('Visit')}'"
            if request.GET.get('Room', ''):
                qry += f" AND mr.\"Room\" = '{request.GET.get('Room')}'"
            if request.GET.get('State', ''):
                for key, value in state_status.items():
                    if value == request.GET.get('State'):
                        qry += f" AND bs.\"State\" = '{key}'"

            # Getting Pagination count for Unmatched tables
            data_pr = UnmachedProcessedView.get_umatched_pr_data(
                self, day, qry)
            pr_total_pages = math.ceil(len(data_pr) / settings.ITEMS_PER_PAGE)
            data_rr = \
                UnmachedProcessedView.get_umatched_rr_data(self, day, "")
            rr_total_pages = math.ceil(len(data_rr) / settings.ITEMS_PER_PAGE)

            context = {
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                'db_data': data,
                'bs_len': bs_len,
                'mr_len': mr_len, 'rr_len': rr_len,
                'pr_len': pr_len,
                'settings': settings_options,
                'filters': filter_options,
                "class": 'reviewProcessedDay',
                "days": days,
                "active": day,
                "shownextday": shownextday,
                "pr_total_pages": 1 if pr_total_pages == 0 \
                    else pr_total_pages,
                "rr_total_pages": 1 if rr_total_pages == 0 \
                    else rr_total_pages,
            }
            return render(request, self.processed_review_template, context)


class UnmachedManifestView(LoginRequiredMixin, View):
    """
    Class for getting unmatched Manifest and blood sample records
    """
    bs_review_table_template = 'review_manifest/bs_unmatched-table.html'
    mf_review_table_template = 'review_manifest/mf_unmatched-table.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the unmatched Manifest and blood sample records
        :param request: request object
        :return: HttpResponse object
        """
        umatched_type = request.GET.get("type", "")
        page = int(request.GET.get('page', 1))
        day, days = UploadView.get_dayformated_and_days(self, request)

        if umatched_type == 'umatched_bs':
            # Getting Unmatched records comparing Blood sample with
            # Manifest records
            mf_cohort_ids = ManifestRecords.objects.filter(
                CollectionDateTime__range=(day.replace(hour=0, \
                    minute=0, second=0, microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0))).\
                        values_list('CohortId', flat=True)[::1]

            if mf_cohort_ids:
                query_results = BloodSample.objects.filter(
                    CreatedAt__range=(day.replace(hour=0, minute=0, \
                        second=0, microsecond=0), day.replace(
                        hour=23, minute=59, second=59, microsecond=0))
                ).exclude(CohortId__iregex=r'(' + '|'.join(mf_cohort_ids)\
                     +')').order_by('CohortId')
            else:
                query_results = BloodSample.objects.filter(
                    CreatedAt__range=(day.replace(hour=0, minute=0, \
                         second=0, microsecond=0), day.replace(
                        hour=23, minute=59, second=59, microsecond=0))
                ).order_by('CohortId')

            paginator = Paginator(query_results, settings.ITEMS_PER_PAGE)

            if paginator.num_pages < page:
                page = paginator.num_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': paginator.num_pages,
                    'current_page': page})

            try:
                results = paginator.page(page)
            except PageNotAnInteger:
                results = paginator.page(1)
            except EmptyPage:
                results = paginator.page(paginator.num_pages)

            return render(request, self.bs_review_table_template, {
                "objects": results.object_list,
                "current_page": page,
                "total_pages": paginator.num_pages
            })

        if umatched_type == 'umatched_mf':
            # Getting Unmatched records comparing Manifest records
            # with Blood sample
            bs_cohort_ids = BloodSample.objects.filter(
                CreatedAt__range=(day.replace(hour=0, minute=0, second=0, \
                     microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0))).\
                        values_list('CohortId', flat=True)[::1]

            if bs_cohort_ids:
                query_results = ManifestRecords.objects.filter(
                    CollectionDateTime__range=(day.replace(hour=0, minute=0, \
                         second=0, microsecond=0), day.replace(
                        hour=23, minute=59, second=59, microsecond=0))
                ).exclude(CohortId__iregex=r'(' + '|'.join(bs_cohort_ids) + \
                     ')').order_by('CohortId')
            else:
                query_results = ManifestRecords.objects.filter(
                    CollectionDateTime__range=(day.replace(hour=0, minute=0, \
                         second=0, microsecond=0), day.replace(
                        hour=23, minute=59, second=59, microsecond=0))
                ).order_by('CohortId')

            if request.GET.get('Room', ''):
                query_results = query_results.filter(
                    Room=request.GET.get('Room'))

            if request.GET.get('Visit', ''):
                query_results = query_results.filter(
                    Visit=request.GET.get('Visit'))

            if request.GET.get('Site', ''):
                query_results = query_results.filter(
                    Site=request.GET.get('Site'))

            paginator = Paginator(query_results, settings.ITEMS_PER_PAGE)

            if paginator.num_pages < page:
                page = paginator.num_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': paginator.num_pages,
                    'current_page': page
                })

            try:
                results = paginator.page(page)
            except PageNotAnInteger:
                results = paginator.page(1)
            except EmptyPage:
                results = paginator.page(paginator.num_pages)

            return render(request, self.mf_review_table_template, {
                "objects": results.object_list,
                "current_page": page,
                "total_pages": paginator.num_pages
            })


class UnmachedReceiptView(LoginRequiredMixin, View):
    """
    Class for getting unmatched Receipt and Manifest records
    """
    bs_review_table_template = 'review_receipt/bsr_unmatched-table.html'
    rr_review_table_template = 'review_receipt/rr_unmatched-table.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the unmatched Receipt and Manifest records
        :param request: request object
        :return: HttpResponse object
        """
        umatched_type = request.GET.get("type", "")
        page = int(request.GET.get('page', 1))
        day, days = UploadView.get_dayformated_and_days(self, request)
        items_per_page = settings.ITEMS_PER_PAGE

        qry = ""

        if request.GET.get('Site', ''):
            qry += f" AND mr.\"Site\" = '{request.GET.get('Site')}'"

        if request.GET.get('Visit', ''):
            qry += f" AND mr.\"Visit\" = '{request.GET.get('Visit')}'"

        if request.GET.get('Room', ''):
            qry += f" AND mr.\"Room\" = '{request.GET.get('Room')}'"

        if umatched_type == 'umatched_bsr':
            # Getting Unmatched records comparing Blood Sample and
            # Manifest records with Receipt
            data = self.get_umatched_bs_data(day, qry)
            total_pages = math.ceil(len(data) / settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': 1 if total_pages == 0 else total_pages,
                    'current_page': 1 if page == 0 else page
                })

            # records based on page to display
            record_start = (page - 1) * items_per_page
            record_end = page * items_per_page
            data = data[record_start:record_end]

            # Converting State, Visit and Site choices to field names
            for row in range(len(data)):
                data[row]['State'] = state_status[data[row]['State']]
                data[row]['Visit'] = visit_choices[data[row]['Visit']]
                data[row]['Site'] = site_choices[data[row]['Site']]

            return render(request, self.bs_review_table_template, {
                "objects": data,
                "current_page": page,
                "total_pages": total_pages
            })

        elif umatched_type == 'umatched_rr':
            # Getting Unmatched records comparing Receipt with
            # Blood Sample and Manifest records
            data = self.get_umatched_rr_data(day, "")

            total_pages = math.ceil(len(data) / settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': 1 if total_pages == 0 else total_pages,
                    'current_page': 1 if page == 0 else page
                })

            # records based on page to display
            record_start = (page - 1) * items_per_page
            record_end = page * items_per_page
            data = data[record_start:record_end]

            return render(request, self.rr_review_table_template, {
                "objects": data,
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages
            })

    def get_umatched_bs_data(self, day, qry=""):
        """
        Method to get unmatched records comparing Blood Sample and
        Manifest records with Receipt
        """
        query = '''
            SELECT "mr"."id",
                bs."CohortId",
                bs."Barcode" as "BloodSampleBarcode",
                bs."AppointmentId",
                bs."SiteNurseEmail",
                bs."Comments",
                bs."CreatedAt",
                bs."State",
                mr."Barcode" as "ManifestBarcode",
                mr."Visit",
                mr."Site",
                mr."Room",
                mr."CollectionDateTime",
                mr."Comments" as "ManifestComments"
            FROM blood_sample_manifestrecords as mr
            INNER JOIN blood_sample_bloodsample as bs \
                ON ( mr."CohortId" = bs."CohortId")
            WHERE mr."Barcode" not in \
                (select "Barcode" from blood_sample_receiptrecords)
                    AND mr."CollectionDateTime" BETWEEN '{}' AND '{}'{}
            order by bs."CohortId";
            '''.format(day.replace(hour=0, minute=0, second=0, microsecond=0)\
                .strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, \
                           microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        return data

    def get_umatched_rr_data(self, day, qry=""):
        """
        Method to get Unmatched records comparing Receipt with
        Blood Sample and Manifest records
        """
        query = '''
            SELECT
                rr."Barcode",
                rr."id",
                rr."Clinic",
                rr."DateTimeTaken",
                rr."TissueSubType",
                rr."ReceivedDateTime",
                rr."Volume",
                rr."VolumeUnit",
                rr."Comments" as "ReceiptComments"
            FROM blood_sample_receiptrecords as rr
            WHERE rr."Barcode" not in (\
                    SELECT
                        "bs"."Barcode"
                    FROM blood_sample_manifestrecords as mr
                    INNER JOIN blood_sample_bloodsample as bs ON \
                        ( mr."CohortId" = bs."CohortId" )
                )
                AND rr."DateTimeTaken" BETWEEN '{}' AND '{}'{}
            order by rr."Barcode";
            '''.format(day.replace(hour=0, minute=0, second=0, \
                microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, \
                           microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        return data


class UnmachedProcessedView(LoginRequiredMixin, View):
    """
    Class for getting unmatched Processed and Receipt records
    """
    rr_review_table_template = 'review_processed/rr_unmatched-table.html'
    pr_review_table_template = 'review_processed/pr_unmatched-table.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the unmatched Processed and Receipt records
        :param request: request object
        :return: HttpResponse object
        """
        umatched_type = request.GET.get("type", "")
        page = int(request.GET.get('page', 1))
        day, days = UploadView.get_dayformated_and_days(self, request)
        items_per_page = settings.ITEMS_PER_PAGE

        qry = ""

        if request.GET.get('Site', ''):
            qry += f" AND mr.\"Site\" = '{request.GET.get('Site')}'"

        if request.GET.get('Visit', ''):
            qry += f" AND mr.\"Visit\" = '{request.GET.get('Visit')}'"

        if request.GET.get('Room', ''):
            qry += f" AND mr.\"Room\" = '{request.GET.get('Room')}'"

        if umatched_type == 'umatched_rr':
            # Getting Unmatched records comparing Blood Sample and
            # Manifest and Receipt records with Processed records
            if request.GET.get('State', ''):
                for key, value in state_status.items():
                    if value == request.GET.get('State'):
                        qry += f" AND bs.\"State\" = '{key}'"

            data = self.get_umatched_rr_data(day, qry)
            total_pages = math.ceil(len(data) / settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': 1 if total_pages == 0 else total_pages,
                    'current_page': 1 if page == 0 else page})

            # records based on page to display
            record_start = (page - 1) * items_per_page
            record_end = page * items_per_page
            data = data[record_start:record_end]

            # Converting State, Visit and Site choices to field names
            for row in range(len(data)):
                data[row]['State'] = state_status[data[row]['State']]
                data[row]['Visit'] = visit_choices[data[row]['Visit']]
                data[row]['Site'] = site_choices[data[row]['Site']]

            return render(request, self.rr_review_table_template, {
                "objects": data,
                "current_page": page,
                "total_pages": total_pages
            })

        elif umatched_type == 'umatched_pr':
            # Getting Unmatched records comparing Processed records with
            # Blood Sample and Manifest and Receipt records
            data = self.get_umatched_pr_data(day, "")
            total_pages = math.ceil(len(data) / settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({
                    'status': 200,
                    'total_pages': 1 if total_pages == 0 else total_pages,
                    'current_page': 1 if page == 0 else page
                })

            # records based on page to display
            record_start = (page - 1) * items_per_page
            record_end = page * items_per_page
            data = data[record_start:record_end]

            # Converting the choice field
            for row in range(len(data)):
                data[row]['SiteHeld'] = site_held_choices[data[row]['SiteHeld']]

            return render(request, self.pr_review_table_template, {
                "objects": data,
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages
            })

    def get_umatched_pr_data(self, day, qry=""):
        """
        Method to grt unmatched records comparing Processed records with
        Blood Sample and Manifest and Receipt records
        """
        query = '''
            SELECT "pr"."id",
                pr."ParentId",
                pr."Barcode",
                pr."ProcessedDateTime",
                pr."Volume",
                pr."NumberOfChildren",
                pr."Comments",
                pr."SiteHeld"
            FROM blood_sample_processedreport as pr
            WHERE pr."ParentId" not in (
                    SELECT
                        rr."SampleId"
                    FROM blood_sample_receiptrecords as rr
                    inner join blood_sample_manifestrecords as mr on \
                        rr."Barcode" = mr."Barcode"
                    inner join blood_sample_bloodsample as bs on \
                        bs."CohortId" = mr."CohortId"
                ) AND pr."ProcessedDateTime" BETWEEN '{}' AND  '{}'{}
            order by pr."ParentId";
            '''.format(day.replace(hour=0, minute=0, second=0, \
                microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, \
                           microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        return data

    def get_umatched_rr_data(self, day, qry=""):
        """
        Method to get unmatched records comparing Blood Sample and
        Manifest and Receipt records with Processed records
        """
        query = '''
            SELECT
                bs."CohortId",
                bs."AppointmentId",
                bs."Barcode" as "BloodSampleBarcode",
                bs."Comments",
                bs."SiteNurseEmail",
                bs."CreatedAt",
                bs."State",
                mr."id" as "ManifestId",
                mr."Barcode" as "ManifestBarcode",
                mr."CohortId" as "ManifestCohortId",
                mr."Site",
                mr."Visit",
                mr."Room",
                mr."CollectionDateTime",
                mr."Comments" as "ManifestComments",
                rr."id" as "ReceiptId",
                rr."Barcode" as "ReceiptBarcode",
                rr."Clinic",
                rr."DateTimeTaken",
                rr."TissueSubType",
                rr."ReceivedDateTime",
                rr."Volume",
                rr."VolumeUnit",
                rr."SampleId",
                rr."Comments" as "ReceiptComments"
            FROM blood_sample_receiptrecords as rr
            inner join blood_sample_manifestrecords as mr on \
                rr."Barcode"=mr."Barcode"
            inner join blood_sample_bloodsample as bs on \
                bs."CohortId"=mr."CohortId"
            WHERE rr."SampleId" not in (
                SELECT
                    "pr"."ParentId"
                FROM blood_sample_processedreport as pr
                join blood_sample_receiptrecords as rr on \
                    pr."ParentId"=rr."SampleId"
                join blood_sample_manifestrecords as mr on \
                    rr."Barcode"=mr."Barcode"
                join blood_sample_bloodsample as bs on \
                    bs."CohortId" = mr."CohortId"
            )
            AND rr."ReceivedDateTime" BETWEEN '{}' AND '{}'{}
            order by bs."CohortId";
            '''.format(day.replace(hour=0, minute=0, second=0, \
                microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, \
                           microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        return data

