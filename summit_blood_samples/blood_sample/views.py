import math
import re
from datetime import datetime
import datetime
import time
import pandas as pd

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import get_template, render_to_string
from django.utils.timezone import make_aware
from django.views import View

from manage_users.models import *
import dateutil.relativedelta
from .models import *

# Import default choices from models
state_status = dict(STATECHOICE)
state_status = {str(k): v for k, v in state_status.items()}

site_choices = dict(SITECHOICE)
site_choices = {str(k): v for k, v in site_choices.items()}

visit_choices = dict(VISITCHOICE)
visit_choices = {str(k): v for k, v in visit_choices.items()}

processing_status = dict(PROCESSING_STATUS)
processing_status = {str(k): v for k, v in processing_status.items()}

sample_type = dict(SAMPLE_TYPE)
sample_type = {str(k): v for k, v in sample_type.items()}


class HomeView(LoginRequiredMixin, View):
    """
    Class for Home page functionality
    """

    template_name = 'home.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the home page view
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.template_name)


class HomeTabView(LoginRequiredMixin, View):
    """
    Class for getting Unresolved day in home tab
    """

    template_name = 'home-tab.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the unresolved days records
        :param request: request object
        :return: HttpResponse object
        """

        # Getting Unmatched records comparing Blood sample with Manifest records
        query = '''
            SELECT DISTINCT DATE(bs."CreatedAt"),to_char(bs."CreatedAt",'Month DD, YYYY' ) as dates
            FROM blood_sample_bloodsample as bs
            left join blood_sample_manifestrecords as mr on bs."CohortId" = mr."CohortId"
            WHERE mr."id" is null
            ORDER BY DATE(bs."CreatedAt")
        '''
        with connection.cursor() as cursor:
            cursor.execute(query)
            bloodsample_dates = [
                re.sub(' +', ' ', row[1])
                for row in cursor.fetchall()
            ]

        # Getting Unmatched records comparing Manifest with Blood Sample records
        query = '''
            SELECT DISTINCT Date(mr."CollectionDateTime"), to_char(mr."CollectionDateTime",'Month DD, YYYY' ) as dates
            FROM "blood_sample_manifestrecords" as mr
            left join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
            WHERE bs."id" is null
            ORDER BY Date(mr."CollectionDateTime") ASC
        '''
        with connection.cursor() as cursor:
            cursor.execute(query)
            un_manifest_dates = [
                re.sub(' +', ' ', row[1])
                for row in cursor.fetchall()
            ]

        # Getting Unmatched records comparing Manifest with Receipt records
        query = '''
            SELECT DISTINCT Date(mr."CollectionDateTime"), to_char(mr."CollectionDateTime",'Month DD, YYYY' ) as dates
            FROM "blood_sample_manifestrecords" as mr
            left join blood_sample_receiptrecords as rr on rr."Barcode" = mr."Barcode"
            WHERE rr."id" is null
            ORDER BY Date(mr."CollectionDateTime") ASC
        '''
        manifest_dates = []

        with connection.cursor() as cursor:
            cursor.execute(query)
            manifest_dates = [
                re.sub(' +', ' ', row[1])
                for row in cursor.fetchall()
            ]

        # Getting Unmatched records comparing Receipt with Manifest records
        query = '''
            SELECT DISTINCT Date(rr."DateTimeTaken"), to_char(rr."DateTimeTaken",'Month DD, YYYY' ) as dates
            FROM "blood_sample_receiptrecords" as rr
            left join blood_sample_manifestrecords as mr on rr."Barcode" = mr."Barcode"
            WHERE mr."id" is null
            ORDER BY Date(rr."DateTimeTaken") ASC
        '''
        un_receipt_dates = []
        with connection.cursor() as cursor:
            cursor.execute(query)
            un_receipt_dates = [
                re.sub(' +', ' ', row[1])
                for row in cursor.fetchall()
            ]

        # Getting Unmatched records comparing Receipt with Processed records
        query = '''
            SELECT
                DISTINCT to_char(rr."DateTimeTaken",'Month DD, YYYY' )
            FROM blood_sample_receiptrecords as rr
            inner join blood_sample_manifestrecords as mr on (rr."Barcode" = mr."Barcode")
            inner join blood_sample_bloodsample as bs on (bs."CohortId" = mr."CohortId")
            WHERE rr."SampleId" not in (SELECT
                                            "pr"."ParentId"
                                        FROM blood_sample_processedreport as pr
                                        join blood_sample_receiptrecords as rr on pr."ParentId" = rr."SampleId"
                                        join blood_sample_manifestrecords as mr on rr."Barcode" = mr."Barcode"
                                        join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
                                    );
            '''

        with connection.cursor() as cursor:
            cursor.execute(query)
            data_pr_rr_unmatched = [row[0]
                                    for row in cursor.fetchall()
                                    ]

        # Getting Unmatched records comparing Processed with Receipt records
        query = '''
            SELECT DISTINCT to_char(pr."ProcessedDateTime",'Month DD, YYYY' )
            FROM blood_sample_processedreport as pr
            WHERE pr."ParentId" not in (
                    SELECT
                        rr."SampleId"
                    FROM blood_sample_receiptrecords as rr
                    inner join blood_sample_manifestrecords as mr on rr."Barcode" = mr."Barcode"
                    inner join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
                ) ;
            '''

        with connection.cursor() as cursor:
            cursor.execute(query)
            data_pr_unmatched = [
                row[0]
                for row in cursor.fetchall()
            ]
        data_pr_rr_unmatched += data_pr_unmatched
        unmatched_pr_data = []
        [unmatched_pr_data.append(
            x) for x in data_pr_rr_unmatched if x not in unmatched_pr_data]

        return render(request, self.template_name, {
            'un_manifest_dates': un_manifest_dates,
            'un_receipt_dates': un_receipt_dates,
            'un_processed_dates': unmatched_pr_data,
            'unmatched_manifest': bloodsample_dates,
            'unmatch_receipt': manifest_dates,
        })


class UploadView(LoginRequiredMixin, View):
    """
    Class for upload functionality
    """

    template_name = 'upload.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the upload view and stats of uploaded samples in a given day
        :param request: request object
        :return: HttpResponse object
        """
        day, days = self.get_dayformated_and_days(request)

        # Disabling the feature dates
        shownextday = datetime.datetime.today().strftime(
            '%d%b%y') in [i.strftime('%d%b%y') for i in days]

        # Getting Blood Samples records count in a given day by CreatedAt field
        blood_samples_loaded = BloodSample.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))

        # Getting Blood Samples records count in a given day by Files imported
        blood_samples_imported = BloodSampleImport.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        blood_samples_imported_cnt = BloodSample.objects.filter(
            ImportId__in=blood_samples_imported.values_list('id', flat=True)[::1]).count()

        # Checking if Last uploaded blood sample file is reviewed or not
        try:
            reviewed = blood_samples_imported.last().Reviewed
        except:
            reviewed = False

        # Getting Manifest records count in a given day by CollectionDateTime field
        manifest_loaded = ManifestRecords.objects.filter(
            CollectionDateTime__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))

        # Getting Manifest records count in a given day by Files imported
        manifest_imported = ManifestImports.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        no_of_files_uploaded = manifest_imported.count()
        manifest_imported_cnt = ManifestRecords.objects.filter(
            ImportId__in=manifest_imported.values_list('id', flat=True)[::1]).count()

        # Getting Receipt records count in a given day by DateTimeTaken field
        receipt_loaded = ReceiptRecords.objects.filter(
            DateTimeTaken__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))

        # Getting Receipt records count in a given day by Files imported
        receipt_imported = ReceiptImports.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        receipt_imported_cnt = ReceiptRecords.objects.filter(
            ImportId__in=receipt_imported.values_list('id', flat=True)[::1]).count()

        # Getting Processed records count in a given day by Files imported
        processed_imported = ProcessedImports.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        processed_imported_cnt = ProcessedReport.objects.filter(
            ImportId__in=processed_imported.values_list('id', flat=True)[::1]).count()

        return render(request, self.template_name, {
            "days": days,
            "blood_samples_cnt": blood_samples_loaded.count(),
            "blood_samples_imported": blood_samples_imported_cnt,
            'manifest_imported': manifest_imported_cnt,
            'manifest_loaded_count': manifest_loaded.count(),
            'receipt_imported': receipt_imported_cnt,
            "receipt_loaded_cnt": receipt_loaded.count(),
            'processed_imported': processed_imported_cnt,
            'active': day,
            'shownextday': shownextday,
            'reviewed': reviewed,
            'class': 'uploadDay',
            'no_of_files_uploaded': no_of_files_uploaded,
        })

    def get_dayformated_and_days(self, request):
        """
        Method to format the given day
        :param request: request object
        :return: formatted day and list of 4 days to display in the navigation
        """

        if 'prev' in request.GET.get('day', ''):
            day = request.GET.get('day')
            day = day.split('-')[1].split(',')
            day = datetime.datetime.strptime(
                day[0].split(' ')[0][:3]+' '+day[0].split(' ')[1]+','+day[1], '%b %d, %Y')
            days = [(day - datetime.timedelta(days=x))
                    for x in range(4)]
            days.reverse()
        elif 'next' in request.GET.get('day', ''):
            day = request.GET.get('day')
            day = day.split('-')[1].split(',')
            day = datetime.datetime.strptime(
                day[0].split(' ')[0][:3]+' '+day[0].split(' ')[1]+','+day[1], '%b %d, %Y')
            days = [(day + datetime.timedelta(days=x))
                    for x in range(4)]

            # Updating the days if future days are present
            try:
                if days.index(datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)) in [0, 1, 2]:
                    days = [(datetime.datetime.today() - datetime.timedelta(days=x))
                            for x in range(4)]
                    days.reverse()
            except:
                # skipping if date is not found
                pass
        else:
            day = request.GET.get(
                'day', datetime.datetime.today().strftime('%b %d, %Y'))
            day = datetime.datetime.today().strftime(
                '%b %d, %Y') if day == 'undefined' else day

            if 'middle' in day:
                firstday = day.split('-')[1]
                firstday = firstday.split(',')
                firstday = datetime.datetime.strptime(
                    firstday[0].split(' ')[0][:3]+' '+firstday[0].split(' ')[1]+','+firstday[1], '%b %d, %Y')
                days = [(firstday - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()
                current_day = day.split('-')[2]
                current_day = current_day.split(',')
                day = datetime.datetime.strptime(
                    current_day[0].split(' ')[0][:3]+' '+current_day[0].split(' ')[1]+','+current_day[1], '%b %d, %Y')
            else:
                day = day.split(',')
                day = datetime.datetime.strptime(
                    day[0].split(' ')[0][:3]+' '+day[0].split(' ')[1]+','+day[1], '%b %d, %Y')
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()
        return make_aware(day), days


class DownloadBloodSampleView(LoginRequiredMixin, View):
    """
    Download blood-sample display and download the csv
    with selected filters and options functionality
    """
    template_name = 'download-blood-sample.html'
    download_blood_table_template = 'download-blood-sample-table.html'

    def get(self, request, *args, **kwargs):
        # storing request in variable request_data
        request_data = dict(request.GET)

        # setting csv variable as default false
        csv = False
        if 'csv' in request_data:
            # if csv is true in request params setting csv to true
            csv = True
        if 'settings' not in request_data:
            # if request params doesn't have settings key, assign default values to settings option
            settings_options = dict(BS=request_data['BloodSample'], MR=request_data['Manifest'],
                                    RR=request_data['Receipt'], PR=request_data['Processed'])
            for table, columns in settings_options.items():
                for column in columns:
                    settings_options[table] = column.split(',')
        else:
            # if exists converting string type to dictionary type using eval keyword
            settings_options = eval(request_data['settings'][0])

        if 'filters' not in request_data:
            # if request params doesn't have filters key, assign default values to filters option
            filter_options = dict(DF=request_data['DateFrom'], DT=request_data['DateTo'], Site=request_data['Site'],
                                  Room=request_data['Room'], Visit=request_data['Visit'], State=request_data['State'])
        else:
            # if exists converting string type to dictionary type using eval keyword
            filter_options = eval(request_data['filters'][0])

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

        # generating a raw sql query based on filters and settings options as requested by user
        query = """ SELECT """
        headers = []

        # selecting the required columns selected by the user
        for table, columns in settings_options.items():
            for column in columns:
                if column != '':
                    # headers for columns in download tab that needs to be displayed
                    headers.append(column)
                if table == 'BS' and column != '':
                    query += "bs.\""+column+"\", "
                if table == 'MR' and column != '':
                    query += "mr.\""+column+"\", "
                if table == 'RR' and column != '':
                    query += "rr.\""+column+"\", "
                if table == 'PR' and column != '':
                    query += "pr.\""+column+"\", "

        query = query[:-2]
        query += """from blood_sample_processedreport as pr
                    right join blood_sample_receiptrecords as rr on pr."ParentId" = rr."SampleId"
                    right join blood_sample_manifestrecords as mr on rr."Barcode" = mr."Barcode"
                    right join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
                """
        extra = ' WHERE '
        date_start = filter_options['DF'][0]
        date_end = filter_options['DT'][0]

        # if no date-from and date -to is not mentioned assigning default values of 1900-01-01, present day by default
        if date_end == '':
            date_end = datetime.datetime.now().strftime("%Y-%m-%d")
            filter_options['DT'][0] = date_end

        if date_start == '':
            last_month = datetime.datetime.strptime(
                date_end, "%Y-%m-%d") - dateutil.relativedelta.relativedelta(months=1)
            date_start = last_month.strftime("%Y-%m-%d")
            filter_options['DF'][0] = date_start

        date_end = datetime.datetime.strptime(
            date_end, "%Y-%m-%d")+datetime.timedelta(days=1)
        date_end = date_end.strftime("%Y-%m-%d")

        # adding filtered values as requested by user
        for filt, value in filter_options.items():
            if filt == 'Site' and value[0] != '':
                val = list(site_choices.keys())[
                    list(site_choices.values()).index(value[0])]
                extra += "mr.\"Site\"='" + val+"' AND "

            if filt == 'Room' and value[0] != '':
                extra += "mr.\"Room\"='" + value[0]+"' AND "

            if filt == 'Visit' and value[0] != '':
                val = list(visit_choices.keys())[
                    list(visit_choices.values()).index(value[0])]
                extra += "mr.\"Visit\"='" + val+"' AND "

            if filt == 'State' and value[0] != '':
                val = list(state_status.keys())[
                    list(state_status.values()).index(value[0])]
                extra += "bs.\"State\"='" + val+"' AND "

        extra += "bs.\"CreatedAt\" BETWEEN '" + \
            date_start + "' AND '" + date_end + "' AND "

        extra = extra[0:-4]
        if extra != ' WH':
            query += extra

        #  ordering the data based on ids and barcode
        query += ' order by mr.\"Barcode\"'
        # the page is set to default to 1 in pagenation
        page = int(request.GET.get('page', 1))
        # setting table to False if page 1
        table = request.GET.get('table', 'False')
        # items per page
        items_per_page = settings.ITEMS_PER_PAGE

        # Creating a cursor object using the cursor() method
        with connection.cursor() as cursor:
            # Executing an SQL function using the execute() method
            cursor.execute(query)
            # Fetch rows using fetchall() method.
            data = cursor.fetchall()
        # total pages calculation based on items per page as mentioned in settings
        total_pages = math.ceil(len(data)/items_per_page)
        # records based on page to display
        record_start = (page-1) * items_per_page
        record_end = page * items_per_page

        if csv:
            items_per_page = len(data)

        # updating the data of enum field with respective data
        if 'State' in settings_options['BS'] or 'Site' in settings_options['MR'] or 'Visit' in settings_options['MR']:
            try:
                ind_state = headers.index('State')
                state_status_choice = True
            except:
                state_status_choice = False
            try:
                ind_site = headers.index('Site')
                site_status = True
            except:
                site_status = False
            try:
                ind_visit = headers.index('Visit')
                visit_status = True
            except:
                visit_status = False
            for row in range(items_per_page):
                if not csv:
                    row += record_start
                    if len(data) <= row:
                        break
                data[row] = list(data[row])
                if state_status_choice:
                    data[row][ind_state] = state_status[data[row][ind_state]]
                if site_status and data[row][ind_site] is not None:
                    data[row][ind_site] = site_choices[data[row][ind_site]]
                if visit_status and data[row][ind_visit] is not None:
                    data[row][ind_visit] = visit_choices[data[row][ind_visit]]
                data[row] = tuple(data[row])

        # display names of columns that display in download tab as headers
        row_headers = {
            'CohortId': 'Cohort id', 'AppointmentId': 'Appointment id', 'SiteNurseEmail': 'Site Nurse Email',
            'CreatedAt': 'Appointment date', 'CollectionDateTime': 'Collection Date Time', 'DateTimeTaken': 'Date Time Taken',
            'SampleId': 'Sample id', 'TissueSubType': 'Tissue Sub Type', 'ReceivedDateTime': 'Received Date Time',
            'VolumeUnit': 'Volume Unit', 'ParentId': 'Parent id', 'ProcessedDateTime': 'Processed Date Time',
            'NumberOfChildren': 'Number Of Children', 'id': 'Id',
        }

        # updating the headers based on the column name
        for i in range(len(headers)):
            if headers[i] in row_headers:
                headers[i] = row_headers[headers[i]]
        if len(data) == 0:
            data = 'No Records to Display'

        # enters if the csv is true and return the downloaded csv
        if csv and data != 'No Records to Display':
            response = HttpResponse(content_type='csv')
            # inserting the headers for the data for csv download
            data.insert(0, tuple(headers))
            template = get_template('csv_download.txt')
            csv_data = data
            download_context = {
                'data': csv_data,
            }
            # download filenmae is generated based on timestamp
            filename = 'BloodSamples_' + datetime.datetime.now().strftime("%Y%m%d%H%M%S")+'.csv'
            content = "attachment; filename=%s" % (filename)
            response['Content-Disposition'] = content
            # response of content that needs to be returned if csv download
            response.write(template.render(download_context))

            return response

        # if more than 1 page will return the data based on the items and page number
        if table == "True":
            return render(request, self.download_blood_table_template, {
                "objects": [headers]+data[record_start:record_end],
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                'db_data': data,
                'bs_len': bs_len,
                'mr_len': mr_len, 'rr_len': rr_len,
                'pr_len': pr_len, 'settings': settings_options, 'filters': filter_options
            })

        # for page 1 display
        context = {
            "current_page": 1 if page == 0 else page,
            "total_pages": 1 if total_pages == 0 else total_pages,
            'db_data': data,
            'bs_len': bs_len, 'mr_len': mr_len, 'rr_len': rr_len, 'pr_len': pr_len,
            'settings': settings_options, 'filters': filter_options,
            'total_records_cnt': len(data)
        }

        return render(request, self.template_name, context)


class DownloadAliquotsView(LoginRequiredMixin, View):
    """
    Aliquots display and download the csv
    """
    template_name = 'download-aliquots.html'
    aliquots_table = 'download-aliquots-table.html'

    def get(self, request, *args, **kwargs):
        # storing request params in variable request_data
        request_data = dict(request.GET)
        # setting csv download to False
        csv = False

        # if csv key in request_data updating the download to True
        if 'csv' in request_data:
            csv = True

        # retrieve data from db using django ORM
        aliquots_data = ProcessedAliquots.objects.all().values_list(
            'SampleId', 'SampleType', 'Volume', 'VolumeUnit', 'PostProcessingStatus').order_by('SampleId', 'SampleType')
        aliquots_data = list(aliquots_data)

        # updating the enum fields w.r.t values
        for row in range(len(aliquots_data)):
            aliquots_data[row] = list(aliquots_data[row])
            aliquots_data[row][-1] = processing_status[aliquots_data[row][-1]]
            aliquots_data[row][1] = sample_type[aliquots_data[row][1]]
            aliquots_data[row] = tuple(aliquots_data[row])

        # if no data to display updating the data
        if len(aliquots_data) == 0:
            aliquots_data = 'No Records to Display'

        headers = ('Parent id', 'Sample type', 'Volume',
                   'Volume unit', 'Post processing status')

        # if csv download is True it works on download
        if csv and len(aliquots_data) != 0:
            response = HttpResponse(content_type='csv')
            aliquots_data.insert(0, headers)
            template = get_template('csv_download.txt')
            csv_data = aliquots_data
            csv_content = {
                'data': csv_data,
            }
            filename = 'Aliquots_' + datetime.datetime.now().strftime("%Y%m%d%H%M%S")+'.csv'
            content = "attachment; filename=%s" % (filename)
            response['Content-Disposition'] = content
            response.write(template.render(csv_content))

            return response

        # setting page number to 1 as default
        page = int(request.GET.get('page', 1))
        # if page 1 setting table to false
        table = request.GET.get('table', 'False')
        # calculating total num of pages
        total_pages = math.ceil(len(aliquots_data)/settings.ITEMS_PER_PAGE)
        # items per page
        items_per_page = settings.ITEMS_PER_PAGE
        # data presentation based on page number
        record_start = (page-1) * items_per_page
        record_end = page * items_per_page

        # if page more than 1 setting the data in page based on number
        if table == "True":
            return render(request, self.aliquots_table, {
                "objects": [headers]+aliquots_data[record_start:record_end],
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                'db_data': aliquots_data
            })

        context = {
            "db_data": aliquots_data,
            "current_page": 1 if page == 0 else page,
            "total_pages": 1 if total_pages == 0 else total_pages,
        }

        return render(request, self.template_name, context)


class SettingsOptionsView(LoginRequiredMixin, View):
    """
    Class for getting settings options
    """
    template_name = 'settings_bloodsample.html'

    def get(self, request, *args, **kwargs):
        """
        Method to return settings columns and filters
        :param request: request object with settings and filters
        :return: HttpResponse object
        """
        settings = eval(request.GET.get('settings'))
        filters = eval(request.GET.get('filters'))
        context = {
            'settings': settings,
            'filters': filters
        }
        return render(request, self.template_name, context)


class FilterOptionsView(LoginRequiredMixin, View):
    """
    Class for getting filter options
    """
    template_name = 'filter_bloodsample.html'

    def get(self, request, *args, **kwargs):
        """
        Method to Return Filter Options
        :param request: request object with settings and filters
        :return: HttpResponse object
        """
        # filter values from request params
        filters = eval(request.GET.get('filters'))
        # settings values from request params
        settings = eval(request.GET.get('settings'))
        date_from = filters['DF'][0]
        date_to = filters['DT'][0]
        # receiving data from db using django ORMs
        receipt_barcode = ReceiptRecords.objects.all().values_list('Barcode')
        visits = ManifestRecords.objects.filter(
            Barcode__in=receipt_barcode).values('Visit').distinct()
        dist_visits = []

        for visit in visits:
            dist_visits += list(visit.values())

        for visit_name in range(len(dist_visits)):
            dist_visits[visit_name] = visit_choices[dist_visits[visit_name]]

        sites = ManifestRecords.objects.filter(
            Barcode__in=receipt_barcode).values('Site').distinct()

        dist_sites = []
        for site in sites:
            dist_sites += list(site.values())

        for site_name in range(len(dist_sites)):
            dist_sites[site_name] = site_choices[dist_sites[site_name]]

        rooms = ManifestRecords.objects.filter(
            Barcode__in=receipt_barcode).values('Room').distinct()

        dist_rooms = []
        for room in rooms:
            dist_rooms += list(room.values())

        # receiving data based on the existing visit, room and site dynamically
        # passing static data of state
        dist_state = ['ACTIVE', 'UNABLE_TO_DRAW', 'UNABLE_TO_PROCESS',
                      'PROCESSED_ON_TIME', 'PROCESSED_NOT_ON_TIME']
        context = {
            'sites': dist_sites,
            'visits': dist_visits,
            'rooms': dist_rooms,
            'filters': filters,
            'settings': settings,
            'states': dist_state,
            'from': date_from,
            'to': date_to
        }
        return render(request, self.template_name, context)


class UploadBloodSampleView(LoginRequiredMixin, View):
    """
    Class for uploading Blood sample file
    """
    template_name = 'upload-blood-sample.html'
    blood_sample_confirm_template = 'confirm-blood-sample.html'
    blood_sample_success_template = 'success-blood-sample.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get upload view of blood sample
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        """
        Method to upload the blood sample
        :param request: request object
        :return: HttpResponse object
        """
        blood_sample_file = request.FILES.get(u'file')

        # Converting input csv file to data frame
        df = pd.read_csv(blood_sample_file)

        # Dropping duplicates in the file
        df = df.drop_duplicates()

        # Validations
        # Columns validation
        if not set(['Id', 'CohortId', 'AppointmentId', 'Barcode', 'User', 'CreatedAt']).issubset(df.columns):
            return JsonResponse({
                'status': 412,
                'message': 'Column names not matching'
            })

        # Input Records Count Validations i.e., Uploaded file should have more number of record compared to database
        if BloodSample.objects.count() >= df.shape[0]:
            return JsonResponse({'status': 412, 'message': 'The uploaded file has less than or equal number of records compared to database records'})

        # CreatedAt column validation
        try:
            df['CreatedAt'] = df['CreatedAt'].apply(lambda x: datetime.datetime.strptime(
                x, "%Y-%m-%dT%H:%M:%SZ"))
        except:
            return JsonResponse({'status': 412, 'message': 'CreatedAt column values are not in expected format'})

        # Getting stats of newly uploading file
        report_ids = BloodSample.objects.values_list('id', flat=True)[
            ::1]
        excel_ids = df.Id.values.tolist()
        new_records = list(set(excel_ids).difference(report_ids))

        if request.GET.get('confirm', '') == 'True':
            # Dropping duplicates when compared to database
            df = df[df['Id'].isin(new_records)]

            # Storing file to uploads folder
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT+'/CurrentAppointmentBlood')
            filename = fs.save(blood_sample_file.name.split(
                '.')[0]+time.strftime("%d%m%Y-%H%M%S")+'.'+blood_sample_file.name.split('.')[1], blood_sample_file)
            # End of storing file

            day, days = UploadView.get_dayformated_and_days(self, request)

            # Uploading file details to BloodSampleImport table
            ImportId = BloodSampleImport.objects.create(
                FilePath="CurrentAppointmentBlood/"+filename,
                OriginalFileName=blood_sample_file.name,
                CreatedBy=request.user,
                CreatedAt=day,
                Deleted=False,
                Reviewed=False,
            )

            # Bulk uploading to BloodSample table
            model_instances = [
                BloodSample(
                    id=record['Id'],
                    CohortId=record['CohortId'],
                    Barcode=record['Barcode'] if re.match(
                        r"^(E[0-9]{6})+$", record['Barcode']) else "",
                    Comments="" if re.match(
                        r"^(E[0-9]{6})+$", record['Barcode']) else record['Barcode'],
                    AppointmentId=record['AppointmentId'],
                    SiteNurseEmail=record['User'],
                    ImportId=ImportId,
                    CreatedAt=make_aware(record['CreatedAt']),
                    State=0 if re.match(
                        r"^(E[0-9]{6})+$", record['Barcode']) else 1,
                ) for index, record in df.iterrows()
            ]
            BloodSample.objects.bulk_create(model_instances)

            return render(request, self.blood_sample_success_template, {"new_records": len(new_records)})

        return render(request, self.blood_sample_confirm_template, {"new_records": len(new_records)})


class UploadManifestView(LoginRequiredMixin, View):
    """
    Class for uploading Manifeset file
    """
    template_name = 'upload-manifest.html'
    blood_sample_confirm_template = 'confirm-manifest.html'
    blood_sample_success_template = 'success-manifest.html'

    def get(self, request, *args, **kwargs):
        """
        Method to upload the Manifest
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        """
        Method to upload the Manifest
        :param request: request object
        :return: HttpResponse object
        """
        manifest_file = request.FILES.get(u'file')

        # Converting input file to data frame
        df = pd.read_excel(manifest_file)

        # Validations

        # File validation
        if not 'Room' in df.iloc[2, 3] and df.iloc[2, 1] != 'Site' and df.iloc[4, 1] != 'Barcode ID' and df.iloc[4, 2] != 'Collection Date & Time' and df.iloc[4, 3] != 'Cohort ID':
            return JsonResponse({'status': 412, 'message': 'Column names not matching'})

        visit = request.POST.get('visit', '')

        # Getting room value from file
        room = int(df.iloc[2, 4]) if isinstance(
            df.iloc[2, 4], float) else df.iloc[2, 4]

        # Getting site value from file and validating it
        site = df.iloc[2, 2]
        if site not in ['FMH', 'KGH', 'Mile End Hospital', 'UCLH']:
            return JsonResponse({'status': 412, 'message': 'Invalid Site'})

        # Dropping rows where all the columns are empty if any exists
        df = df.iloc[5:-1, 1:-1].dropna()

        # Dropping duplicates in the file
        df = df.drop_duplicates()

        df.columns = ['Barcode', 'CollectionDateTime', 'CohortId']

        # Validating CollectionDateTime column
        if True in (df['CollectionDateTime'].map(type) != datetime.datetime).tolist():
            return JsonResponse({'status': 412, 'message': 'CollectionDateTime column values are not in expected format'})

        # Validating removing extra space if any in CohortId column
        df['CohortId'] = df['CohortId'].apply(lambda x: x.strip())

        # Validating CohortId value length
        if True in (df['CohortId'].map(len) != 7).tolist():
            return JsonResponse({'status': 412, 'message': 'CohortId column values length are not in expected format'})

        # Getting stats of uploaded file
        manifest_db_df = pd.DataFrame(
            list(ManifestRecords.objects.values('Barcode', 'CollectionDateTime', 'CohortId')))

        blood_sample_cohort = BloodSample.objects.values_list('CohortId', flat=True)[
            ::1]
        df_cohort = df['CohortId'].tolist()

        # Records count that are not found in blood samples table
        record_not_found_cnt = len(
            set(df_cohort).difference(blood_sample_cohort))
        duplicates_cnt = 0

        # Records count that are found in blood samples table
        record_found_cnt = len(df_cohort)-record_not_found_cnt

        unique_df = df

        if not manifest_db_df.shape == (0, 0):
            # Dropping duplicates in the file comparing with the manifest table records
            unique_df = df[~df.Barcode.isin(manifest_db_df.Barcode.values) & ~df.CohortId.isin(
                manifest_db_df.CohortId.values) & ~df.CollectionDateTime.isin(manifest_db_df.CollectionDateTime.values)]
            # Getting duplicated count comparing with the database
            duplicates_cnt = df.shape[0]-unique_df.shape[0]

        if request.GET.get('confirm', '') == 'True':
            # Storing file to the uploads folder
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT+'/Manifests')
            filename = fs.save(manifest_file.name.split(
                '.')[0]+time.strftime("%d%m%Y-%H%M%S")+'.'+manifest_file.name.split('.')[1], manifest_file)
            # End of storing file

            day, days = UploadView.get_dayformated_and_days(self, request)

            # Uploading file details to ManifestImports table
            ImportId = ManifestImports.objects.create(
                FilePath="Manifests/"+filename,
                OriginalFileName=manifest_file.name,
                CreatedBy=request.user,
                CreatedAt=day,
                Deleted=False
            )

            # Bulk uploading to ManifestRecords table
            model_instances = [
                ManifestRecords(
                    Visit=visit,
                    ImportId=ImportId,
                    Site=dict((v, k)
                              for k, v in site_choices.items()).get(site),
                    Room=room,
                    CohortId=record[2].strip(),
                    Barcode=record[0],
                    CollectionDateTime=make_aware(record[1])
                ) for index, record in unique_df.iterrows()
            ]
            ManifestRecords.objects.bulk_create(model_instances)

            return render(request, self.blood_sample_success_template, {"duplicates_cnt": duplicates_cnt,
                                                                        "record_not_found_cnt": record_not_found_cnt,
                                                                        "record_found_cnt": record_found_cnt, })

        return render(request, self.blood_sample_confirm_template, {
            "duplicates_cnt": duplicates_cnt,
            "record_not_found_cnt": record_not_found_cnt,
            "record_found_cnt": record_found_cnt,
        })


class UploadReceiptView(LoginRequiredMixin, View):
    """
    Class for uploading Receipt file
    """
    template_name = 'upload-receipt.html'
    receipt_confirm_template = 'confirm-receipt.html'
    receipt_success_template = 'success-receipt.html'

    def get(self, request, *args, **kwargs):
        """
        Method to upload the Receipt
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        """
        Method to upload the Receipt
        :param request: request object
        :return: HttpResponse object
        """
        receipt_file = request.FILES.get(u'file')

        # Converting input file to data frame
        df = pd.read_csv(receipt_file)

        # Dropping duplicates in the file
        df = df.drop_duplicates()

        # Validations

        # File validation
        if not set(['Participant ID', 'Clinic', 'DateTime Taken', 'Sample ID',
                    'Tissue sub-type', 'Received DateTime', 'Volume', 'Volume Unit',
                    'Condition']).issubset(df.columns):
            return JsonResponse({'status': 412, 'message': 'Column names not matching'})

        # Validating DateTime Taken column
        try:
            df['DateTime Taken'] = df['DateTime Taken'].apply(lambda x: datetime.datetime.strptime(
                x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({'status': 412, 'message': 'DateTime Taken column values are not in expected format'})

        # Validating Received DateTime column
        try:
            df['Received DateTime'] = df['Received DateTime'].apply(lambda x: datetime.datetime.strptime(
                x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({'status': 412, 'message': 'Received DateTime column values are not in expected format'})

        # Validating Volume Unit column
        if True in (df['Volume Unit'] != 'uL').tolist():
            return JsonResponse({'status': 412, 'message': 'Volume Unit column values are not an uL'})

        # Validating Tissue sub-type column
        if True in (df['Tissue sub-type'] != 'EDTA').tolist():
            return JsonResponse({'status': 412, 'message': 'Tissue sub-type column values are not an EDTA'})

        # Validating and converting Clinic column
        clinic_mapping = {
            'uk biocentre signature': 'Manifest Signature',
            'uch - university college london hospital': 'UCLH',
            'mile end hospital': 'Mile End Hospital',
            'finchley memorial': 'FMH',
            'king george hospital ilford': 'KGH',
        }
        try:
            df['Clinic'] = df['Clinic'].apply(
                lambda x:
                    clinic_mapping[x.lower()])
        except:
            return JsonResponse({'status': 412, 'message': 'Clinic column values are not in expected format'})

        # Getting stats of the uploaded file
        df['DateTime Taken compare'] = df['DateTime Taken'].apply(
            lambda x: x.strftime('%d/%m/%Y %H:%M'))
        manifest_db_df = pd.DataFrame(ManifestRecords.objects.all().values())
        manifest_db_df['CollectionDateTime'] = manifest_db_df['CollectionDateTime'].apply(
            lambda x: x.strftime('%d/%m/%Y %H:%M'))
        manifest_db_filtered = manifest_db_df[manifest_db_df['CohortId'].isin(BloodSample.objects.values_list(
            'CohortId', flat=True)[::1])]

        # Getting records already present in the database
        manifest_match = df[df['Participant ID'].isin(manifest_db_filtered.Barcode.values) & df['Clinic'].isin(
            manifest_db_filtered.Site.values) & df['DateTime Taken compare'].isin(manifest_db_filtered.CollectionDateTime.values)]
        record_found_cnt = manifest_match.shape[0]

        # Getting records where there is mismatch on manifest site with uploaded receipt Clinic
        mismatch_site = df[df['Participant ID'].isin(manifest_db_df.Barcode.values) & ~df['Clinic'].isin(
            manifest_db_df.Site.values)]
        mismatch_site_found_cnt = mismatch_site.shape[0]

        # Getting records where there is mismatch on Receipt DateTime Taken with Manifest CollectionDateTime
        mismatch_blood_draw = df[df['Participant ID'].isin(manifest_db_df.Barcode.values) & ~df['DateTime Taken compare'].isin(
            manifest_db_df.CollectionDateTime.values)]
        mismatch_blood_draw_found_cnt = mismatch_blood_draw.shape[0]

        # Checking number of Receipt records barcodes not existing in Manifest table
        receipt_barcode_existance = df[~df['Participant ID'].isin(
            manifest_db_df.Barcode.values)].shape[0]

        # Getting total records
        total_records = df.shape[0]

        if request.GET.get('confirm', '') == 'True':
            del df['DateTime Taken compare']

            # storing file
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT+'/Receipt')
            filename = fs.save(receipt_file.name.split(
                '.')[0]+time.strftime("%d%m%Y-%H%M%S")+'.'+receipt_file.name.split('.')[1], receipt_file)
            # End of storing file

            day, days = UploadView.get_dayformated_and_days(self, request)

            # Uploading file details to ReceiptImports table
            ImportId = ReceiptImports.objects.create(
                FilePath="Receipt/"+filename,
                OriginalFileName=receipt_file.name,
                CreatedBy=request.user,
                CreatedAt=day,
                Deleted=False
            )

            # Dropping duplicates in file comparing with ReceiptRecords table
            receipt_barcode = ReceiptRecords.objects.values_list('Barcode', flat=True)[
                ::1]
            df = df[~df['Participant ID'].isin(receipt_barcode)]

            # Bulk uploading to ReceiptRecords table
            model_instances = [
                ReceiptRecords(
                    Barcode=record['Participant ID'],
                    Clinic=record['Clinic'],
                    DateTimeTaken=make_aware(record['DateTime Taken']),
                    SampleId=record['Sample ID'],
                    TissueSubType=record['Tissue sub-type'],
                    ReceivedDateTime=make_aware(record['Received DateTime']),
                    Volume=record['Volume'],
                    VolumeUnit=record['Volume Unit'],
                    Condition=record['Condition'],
                    ImportId=ImportId,
                ) for index, record in df.iterrows()
            ]
            ReceiptRecords.objects.bulk_create(model_instances)

            return render(request, self.receipt_success_template, {
                "record_found_cnt": record_found_cnt,
                "mismatch_site_found_cnt": mismatch_site_found_cnt,
                "mismatch_blood_draw_found_cnt": mismatch_blood_draw_found_cnt,
                "receipt_barcode_existance": receipt_barcode_existance,
            })

        return render(request, self.receipt_confirm_template, {
            "total_records": total_records,
            "record_found_cnt": record_found_cnt,
            "mismatch_site_found_cnt": mismatch_site_found_cnt,
            "mismatch_blood_draw_found_cnt": mismatch_blood_draw_found_cnt,
            "receipt_barcode_existance": receipt_barcode_existance,
        })


class UploadProcessedView(LoginRequiredMixin, View):
    """
    Class for uploading Processed file
    """
    template_name = 'upload-processed.html'
    receipt_confirm_template = 'confirm-processed.html'
    receipt_success_template = 'success-processed.html'

    def get(self, request, *args, **kwargs):
        """
        Method to upload the Processed
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        """
        Method to upload the Processed
        :param request: request object
        :return: HttpResponse object
        """
        processed_file = request.FILES.get(u'file')

        # Converting input file to data frame
        df = pd.read_csv(processed_file)

        # Dropping duplicates in the file
        df = df.drop_duplicates()

        # Validations

        # File validation
        if not set(['Participant ID', 'Parent ID', 'Sample ID', 'Tissue Sub-Type',
                    'Sample Type', 'Received DateTime', 'Processed Date Time', 'Volume',
                    'Volume Unit', 'No. of Children']).issubset(df.columns):
            return JsonResponse({'status': 412, 'message': 'Column names not matching'})

        # Validating Sample Type column
        if set(df['Sample Type'].unique().tolist()) != set(['RBC', 'Plasma', 'BuffyCoat', 'Whole Blood']):
            return JsonResponse({'status': 412, 'message': 'Sample Type column values are not having expected values'})

        # splitting processed and aliquots from the file
        parent_df = df[df['Parent ID'] == 'No Parent']
        child_df = df[df['Parent ID'] != 'No Parent']

        # Validating Processed Date Time column
        try:
            parent_df['Processed Date Time'].apply(lambda x: datetime.datetime.strptime(
                x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({'status': 412, 'message': 'Processed Date Time column values are not in expected format'})

        # Validating Received Date Time column
        try:
            parent_df['Received DateTime'].apply(lambda x: datetime.datetime.strptime(
                x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({'status': 412, 'message': 'Received DateTime column values are not in expected format'})

        # Validating Volume Unit column
        if True in (parent_df['Volume Unit'] != 'uL').tolist():
            return JsonResponse({'status': 412, 'message': 'Volume Unit column with Parent ID, values are not an uL'})

        if True in (df[df['Parent ID'] != 'No Parent']['Volume Unit'] != 'ul').tolist():
            return JsonResponse({'status': 412, 'message': 'Volume Unit column with no Parent ID, values are not an ul'})

        # Validating Sample Type column
        if True in (parent_df['Sample Type'] != 'Whole Blood').tolist():
            return JsonResponse({'status': 412, 'message': 'Sample Type column with Parent ID, values are not an Whole Blood'})

        if set(df[df['Parent ID'] != 'No Parent']
                ['Sample Type'].unique().tolist()) != set(['RBC', 'Plasma', 'BuffyCoat']):
            return JsonResponse({'status': 412, 'message': 'Sample Type column with no Parent ID, values are not having expected values'})

        # Validating Tissue Sub-Type column
        if True in (df['Tissue Sub-Type'] != 'EDTA').tolist():
            return JsonResponse({'status': 412, 'message': 'Tissue sub-type column values are not an EDTA'})

        # Validating No. of Children column
        if True in (df['No. of Children'].map(type) != int).tolist():
            return JsonResponse({'status': 412, 'message': 'No. of Children column values are not having expected values'})

        # Validating No. of Children column
        if True in (df['Volume'].map(type) != float).tolist():
            return JsonResponse({'status': 412, 'message': 'Volume column values are not having expected values'})

        # Getting stats of the uploaded file
        total_records = parent_df.shape[0]

        manifest_db_df = pd.DataFrame(ManifestRecords.objects.filter(
            Barcode__in=parent_df['Participant ID'].tolist()).values())

        # Checking number of Parent records barcodes not existing in Manifest table
        receipt_barcode_existance = total_records - manifest_db_df.shape[0]

        # Getting records that are processed outside of 36 hrs
        manifest_parent_df = parent_df[parent_df['Participant ID'].isin(
            manifest_db_df.Barcode.values)]
        manifest_db_df = manifest_db_df.rename(
            columns={'Barcode': 'Participant ID'})
        manifest_db_df = pd.merge(
            manifest_parent_df, manifest_db_df, on='Participant ID')
        manifest_db_df['Processed Date Time'] = manifest_db_df['Processed Date Time'].apply(lambda x: datetime.datetime.strptime(
            x, "%d/%m/%Y %H:%M"))
        manifest_db_df['CollectionDateTime'] = manifest_db_df['CollectionDateTime'].apply(lambda x: datetime.datetime.strftime(
            x, "%d/%m/%Y %H:%M"))
        manifest_db_df['CollectionDateTime'] = manifest_db_df['CollectionDateTime'].apply(lambda x: datetime.datetime.strptime(
            x, "%d/%m/%Y %H:%M"))

        manifest_db_df['greaterthan_36hrs'] = ''
        for index, row in manifest_db_df.iterrows():
            manifest_db_df.at[index, 'greaterthan_36hrs'] = True if (
                manifest_db_df['Processed Date Time'].iloc[index]-manifest_db_df['CollectionDateTime'].iloc[index]).total_seconds() // (settings.PROCESSING_HOURS*100) > settings.PROCESSING_HOURS else False

        if request.GET.get('confirm', '') == 'True':
            # storing file
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT+'/Processed')
            filename = fs.save(processed_file.name.split(
                '.')[0]+time.strftime("%d%m%Y-%H%M%S")+'.'+processed_file.name.split('.')[1], processed_file)
            # End of storing file

            day, days = UploadView.get_dayformated_and_days(self, request)

            # Uploading file details to ProcessedImports table
            ImportId = ProcessedImports.objects.create(
                FilePath="Processed/"+filename,
                OriginalFileName=processed_file.name,
                CreatedBy=request.user,
                CreatedAt=day,
                Deleted=False
            )

            # Dropping duplicates in file comparing with ProcessedReport table
            processed_barcode = ProcessedReport.objects.values_list('Barcode', flat=True)[
                ::1]
            parent_df = parent_df[~parent_df['Participant ID'].isin(
                processed_barcode)]

            parent_df['Processed Date Time'] = parent_df['Processed Date Time'].apply(
                lambda x: datetime.datetime.strptime(x, "%d/%m/%Y %H:%M"))
            parent_df['Received DateTime'] = parent_df['Received DateTime'].apply(
                lambda x: datetime.datetime.strptime(x, "%d/%m/%Y %H:%M"))

            # Bulk uploading to ProcessedReport table
            model_instances = [
                ProcessedReport(
                    Barcode=record['Participant ID'],
                    ParentId=ReceiptRecords.objects.filter(
                        Barcode=record['Participant ID']).first().SampleId,
                    TissueSubType=record['Tissue Sub-Type'],
                    ReceivedDateTime=make_aware(record['Received DateTime']),
                    ProcessedDateTime=make_aware(
                        record['Processed Date Time']),
                    Volume=record['Volume'],
                    VolumeUnit=record['Volume Unit'],
                    NumberOfChildren=record['No. of Children'],
                    ImportId=ImportId,
                ) for index, record in parent_df.iterrows()
            ]
            ProcessedReport.objects.bulk_create(model_instances)

            # Dropping duplicates in file comparing with ProcessedAliquots table
            processed_aliquots_barcode = ProcessedAliquots.objects.values_list('SampleIdFile', flat=True)[
                ::1]
            child_df = child_df[~child_df['Sample ID'].isin(
                processed_aliquots_barcode)]

            # Bulk uploading to ProcessedAliquots table
            model_instances = [
                ProcessedAliquots(
                    SampleType=dict((v, k) for k, v in sample_type.items()).get(
                        record["Sample Type"]),
                    Volume=record['Volume'],
                    VolumeUnit=record['Volume Unit'],
                    PostProcessingStatus=0,
                    SampleId=ProcessedReport.objects.filter(
                        Barcode=record['Participant ID']).first().ParentId,
                    SampleIdFile=record['Sample ID'],
                ) for index, record in child_df.iterrows()
            ]
            ProcessedAliquots.objects.bulk_create(model_instances)

            manifest_db_df = manifest_db_df[manifest_db_df['Participant ID'].isin(
                parent_df['Participant ID'].tolist())]

            # Updating the Bloodsamples State based on processing time to
            # PROCESSED_ON_TIME or PROCESSED_NOT_ON_TIME
            processed_not_on_time = 0
            for index, row in manifest_db_df.iterrows():
                blood_samples = BloodSample.objects.filter(
                    CohortId=row['CohortId'])
                for sample in blood_samples:
                    if row['greaterthan_36hrs'] == True:
                        sample.State = 4
                        sample.save()
                        processed_not_on_time += 1
                    elif row['greaterthan_36hrs'] == False:
                        sample.State = 3
                        sample.save()

            # Updating the Bloodsamples State if Aliquots are less than 6 to
            # UNABLE_TO_PROCESS
            for index, row in parent_df[parent_df['No. of Children'] < 6].iterrows():
                blood_samples = BloodSample.objects.filter(
                    Barcode=row['Participant ID'])
                for sample in blood_samples:
                    sample.State = 2
                    sample.save()

            # Mailing all blood sample Data Manager if any PROCESSED_NOT_ON_TIME records are uploaded
            if processed_not_on_time > 0:
                msg_html = render_to_string(
                    'mail-aliquots-less.html', {'processed_not_on_time': processed_not_on_time,
                                                'referer': request.headers['Referer'][:-1]})
                send_mail(
                    'Blood Samples - Uploaded Processed records which are not processed under 36 hours',
                    msg_html,
                    settings.DEFAULT_FROM_EMAIL,
                    [i.user_id.email for i in UserRoles.objects.filter(role_id__in=[
                        2])],  # This should be list of from users
                    html_message=msg_html,
                )

            return render(request, self.receipt_success_template, {
                "total_records": total_records,
                "processed_on_time": manifest_db_df.greaterthan_36hrs[manifest_db_df.greaterthan_36hrs == False].count(),
                "processed_not_on_time": manifest_db_df.greaterthan_36hrs[manifest_db_df.greaterthan_36hrs == True].count(),
                "less_aliquots_cnt": parent_df['No. of Children'][parent_df['No. of Children'] < 6].count(),
                "barcode_existance": receipt_barcode_existance,
            })

        return render(request, self.receipt_confirm_template, {
            "total_records": total_records,
            "processed_on_time": manifest_db_df.greaterthan_36hrs[manifest_db_df.greaterthan_36hrs == False].count(),
            "processed_not_on_time": manifest_db_df.greaterthan_36hrs[manifest_db_df.greaterthan_36hrs == True].count(),
            "less_aliquots_cnt": parent_df['No. of Children'][parent_df['No. of Children'] < 6].count(),
            "barcode_existance": receipt_barcode_existance,
        })


class ReviewView(LoginRequiredMixin, View):
    """
    Class for reviewing all the uploaded files with day navigation
    """

    blood_sample_review_template = 'review_blood_sample/blood-sample-review.html'
    blood_sample_review_table_template = 'review_blood_sample/blood-sample-table.html'
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
                CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0)))

            # Checking latest uploaded sample file is reviewed or not
            if blood_samples_imported.count() > 0:
                sample_import_latest = blood_samples_imported.last()
                # If not reviewed changing the Reviewed column to True
                if not sample_import_latest.Reviewed:
                    sample_import_latest.Reviewed = True
                    sample_import_latest.save()

            # When first opening the review popup updating the day to the latest day where records are available.
            # This will avoid user to unnecessary navigation to the day where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and BloodSample.objects.count():
                day = BloodSample.objects.all().order_by('-CreatedAt').first().CreatedAt
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()

            # Getting the BloodSample records
            query_results = BloodSample.objects.filter(
                CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0))).order_by('CreatedAt', 'CohortId', 'Barcode')

            # Getting results based on pagination
            paginator = Paginator(query_results, settings.ITEMS_PER_PAGE)

            if table == "True":
                try:
                    results = paginator.page(page)
                except PageNotAnInteger:
                    results = paginator.page(1)
                except EmptyPage:
                    results = paginator.page(paginator.num_pages)
                return render(request, self.blood_sample_review_table_template, {
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
            # When first opening the review popup updating the day to the latest day where records are there.
            # This will avoid user to unnecessary navigation to the day where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and ManifestRecords.objects.count():
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
                INNER JOIN blood_sample_bloodsample as bs ON ( mr."CohortId" = bs."CohortId")
                WHERE mr."CollectionDateTime" BETWEEN '{}' AND '{}'{}
                order by bs."CohortId";
                '''.format(day.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                           day.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                data = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

            items_per_page = settings.ITEMS_PER_PAGE
            total_pages = math.ceil(len(data)/items_per_page)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': 1 if total_pages == 0 else total_pages, "current_page": 1 if page == 0 else page, })

            if table == "True":
                record_start = (page-1) * items_per_page
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
                left join blood_sample_manifestrecords as mr on bs."CohortId" = mr."CohortId"
                WHERE mr."id" is null AND bs."CreatedAt" BETWEEN '{}' AND '{}'
            '''.format(
                day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0))
            with connection.cursor() as cursor:
                cursor.execute(query)
                data_count = cursor.fetchall()[0][0]
                bs_unmatched_total_pages = math.ceil(
                    data_count/settings.ITEMS_PER_PAGE)

            # Comparing Manifest with Blood Sample

            query = '''
                SELECT count(1)
                FROM blood_sample_manifestrecords as mr
                left join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
                WHERE mr."id" is null AND mr."CollectionDateTime" BETWEEN '{}' AND '{}'
            '''.format(
                day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0))
            with connection.cursor() as cursor:
                cursor.execute(query)
                data_count = cursor.fetchall()[0][0]
                mf_unmatched_total_pages = math.ceil(
                    data_count/settings.ITEMS_PER_PAGE)

            return render(request, self.manifest_review_template, {
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                "bs_total_pages": 1 if bs_unmatched_total_pages == 0 else bs_unmatched_total_pages,
                "mf_total_pages": 1 if mf_unmatched_total_pages == 0 else mf_unmatched_total_pages,
                "days": days,
                "active": day,
                "shownextday": shownextday,
                "class": 'reviewManifestDay',
            })

        if review_type == "receipt":
            # When first opening the review popup updating the day to the latest day where records are there.
            # This will avoid user to unnecessary navigation to the day where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and ReceiptRecords.objects.count():
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
                inner join blood_sample_manifestrecords as mr on (rr."Barcode"=mr."Barcode")
                inner join blood_sample_bloodsample as bs on (bs."CohortId"=mr."CohortId")
                WHERE rr."DateTimeTaken" BETWEEN '{}' AND '{}' {}
                order by bs."CohortId";
                '''.format(day.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                           day.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                data = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

            items_per_page = settings.ITEMS_PER_PAGE
            total_pages = math.ceil(len(data)/settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': 1 if total_pages == 0 else total_pages, "current_page": 1 if page == 0 else page, })

            if table == "True":
                record_start = (page-1) * items_per_page
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
            bs_total_pages = math.ceil(len(data_bs)/settings.ITEMS_PER_PAGE)

            # Comaring Receipt with Blood sample and Manifest
            data_rr = UnmachedReceiptView.get_umatched_rr_data(self, day, "")
            rr_total_pages = math.ceil(len(data_rr)/settings.ITEMS_PER_PAGE)

            return render(request, self.receipt_review_template, {
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                "bsr_total_pages": 1 if bs_total_pages == 0 else bs_total_pages,
                "rr_total_pages": 1 if rr_total_pages == 0 else rr_total_pages,
                "days": days,
                "active": day,
                "shownextday": shownextday,
                "class": 'reviewReceiptDay',
            })

        if review_type == "processed":
            # When first opening the review popup updating the day to the latest day where records are there.
            # This will avoid user to unnecessary navigation to the day where he last uploaded
            if request.GET.get('firstOpen', 'False') == "True" and ProcessedReport.objects.count():
                day = ProcessedReport.objects.all().order_by(
                    '-ProcessedDateTime').first().ProcessedDateTime
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()

            # Getting settings options
            settings_options = dict(BS=[request.GET.get('BloodSample', "CohortId,Barcode,CreatedAt,Comments,State")], MR=[request.GET.get('Manifest', "Visit,Site,Room,Barcode")],
                                    RR=[request.GET.get('Receipt', "SampleId,Clinic")], PR=[request.GET.get('Processed', "ParentId,TissueSubType,ProcessedDateTime,ReceivedDateTime,Volume,NumberOfChildren,Comments")])
            for table, columns in settings_options.items():
                for column in columns:
                    settings_options[table] = column.split(',')

            # Getting filters options
            filter_options = dict(DF=[""], DT=[""], Site=[request.GET.get('Site', '')],
                                  Room=[request.GET.get('Room', '')], Visit=[request.GET.get('Visit', '')], State=[request.GET.get('State', '')])

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

            # generating a raw sql query based on filters and settings options as requested by user
            query = """ SELECT """
            headers = []

            # selecting the required columns selected by the user
            for table, columns in settings_options.items():
                for column in columns:
                    if column != '':
                        # headers for columns in download tab that needs to be displayed
                        headers.append(column)
                    if table == 'BS' and column != '':
                        query += "bs.\""+column+"\", "
                    if table == 'MR' and column != '':
                        query += "mr.\""+column+"\", "
                    if table == 'RR' and column != '':
                        query += "rr.\""+column+"\", "
                    if table == 'PR' and column != '':
                        query += "pr.\""+column+"\", "

            query += "bs.\"id\" as \"BloodSampleId\", pr.\"id\" as \"ProcessedId\", "

            query = query[:-2]
            query += """from blood_sample_processedreport as pr
                        join blood_sample_receiptrecords as rr on pr."ParentId" = rr."SampleId"
                        join blood_sample_manifestrecords as mr on rr."Barcode" = mr."Barcode"
                        join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
                    """
            extra = ' WHERE '

            # adding filtered values as requested by user
            for filt, value in filter_options.items():
                if filt == 'Site' and value[0] != '':
                    extra += "mr.\"Site\"='" + value[0]+"' AND "

                if filt == 'Room' and value[0] != '':
                    extra += "mr.\"Room\"='" + value[0]+"' AND "

                if filt == 'Visit' and value[0] != '':
                    extra += "mr.\"Visit\"='" + value[0]+"' AND "

                if filt == 'State' and value[0] != '':
                    val = list(state_status.keys())[
                        list(state_status.values()).index(value[0])]
                    extra += "bs.\"State\"='" + val+"' AND "

            extra += """ pr.\"ProcessedDateTime\" BETWEEN '{}' AND '{}' AND """.format(day.replace(hour=0, minute=0, second=0, microsecond=0),
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

            # display names of columns that display in download tab as headers
            row_headers = {
                'CohortId': 'Cohort id', 'AppointmentId': 'Appointment id', 'SiteNurseEmail': 'Site Nurse Email',
                'CreatedAt': 'Appointment date', 'CollectionDateTime': 'Collection Date Time', 'DateTimeTaken': 'Date Time Taken',
                'SampleId': 'Sample id', 'TissueSubType': 'Tissue Sub Type', 'ReceivedDateTime': 'Received Date Time',
                'VolumeUnit': 'Volume Unit', 'ParentId': 'Parent id', 'ProcessedDateTime': 'Processed Date Time',
                'NumberOfChildren': 'Number Of Children', 'id': 'Id'}

            # updating the headers based on the column name
            for i in range(len(headers)):
                if headers[i] in row_headers:
                    headers[i] = row_headers[headers[i]]

            page = int(request.GET.get('page', 1))
            table = request.GET.get('table', 'False')

            total_pages = math.ceil(len(data)/settings.ITEMS_PER_PAGE)
            items_per_page = settings.ITEMS_PER_PAGE
            record_start = (page-1) * items_per_page
            record_end = page * items_per_page

            if len(data) != 0:
                headers.extend(['BloodSample Id', 'Processed Id'])
                data = [headers]+data[record_start:record_end]

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': 1 if total_pages == 0 else total_pages, "current_page": 1 if page == 0 else page, })

            if table == "True":
                return render(request, self.processed_review_table_template, {
                    "objects": data,
                    "current_page": 1 if page == 0 else page,
                    "total_pages": 1 if total_pages == 0 else total_pages,
                    'db_data': data,
                    'bs_len': bs_len,
                    'mr_len': mr_len, 'rr_len': rr_len,
                    'pr_len': pr_len, 'settings': settings_options, 'filters': filter_options,
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
            pr_total_pages = math.ceil(len(data_pr)/settings.ITEMS_PER_PAGE)
            data_rr = UnmachedProcessedView.get_umatched_rr_data(self, day, "")
            rr_total_pages = math.ceil(len(data_rr)/settings.ITEMS_PER_PAGE)

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
                "pr_total_pages": 1 if pr_total_pages == 0 else pr_total_pages,
                "rr_total_pages": 1 if rr_total_pages == 0 else rr_total_pages,
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
            # Getting Unmatched records comparing Blood sample with Manifest records
            mf_cohort_ids = ManifestRecords.objects.filter(
                CollectionDateTime__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0))).values_list('CohortId', flat=True)[::1]

            if mf_cohort_ids:
                query_results = BloodSample.objects.filter(
                    CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                        hour=23, minute=59, second=59, microsecond=0))
                ).exclude(CohortId__iregex=r'(' + '|'.join(mf_cohort_ids) + ')').order_by('CohortId')
            else:
                query_results = BloodSample.objects.filter(
                    CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                        hour=23, minute=59, second=59, microsecond=0))
                ).order_by('CohortId')

            paginator = Paginator(query_results, settings.ITEMS_PER_PAGE)

            if paginator.num_pages < page:
                page = paginator.num_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': paginator.num_pages, "current_page": page})

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
            # Getting Unmatched records comparing Manifest records with Blood sample
            bs_cohort_ids = BloodSample.objects.filter(
                CreatedAt__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                    hour=23, minute=59, second=59, microsecond=0))).values_list('CohortId', flat=True)[::1]

            if bs_cohort_ids:
                query_results = ManifestRecords.objects.filter(
                    CollectionDateTime__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
                        hour=23, minute=59, second=59, microsecond=0))
                ).exclude(CohortId__iregex=r'(' + '|'.join(bs_cohort_ids) + ')').order_by('CohortId')
            else:
                query_results = ManifestRecords.objects.filter(
                    CollectionDateTime__range=(day.replace(hour=0, minute=0, second=0, microsecond=0), day.replace(
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
                return JsonResponse({'status': 200, 'total_pages': paginator.num_pages, "current_page": page})

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
            # Getting Unmatched records comparing Blood Sample and Manifest records with Receipt
            data = self.get_umatched_bs_data(day, qry)
            total_pages = math.ceil(len(data)/settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': 1 if total_pages == 0 else total_pages, "current_page": 1 if page == 0 else page})

            record_start = (page-1) * items_per_page
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
            # Getting Unmatched records comparing Receipt with Blood Sample and Manifest records
            data = self.get_umatched_rr_data(day, "")

            total_pages = math.ceil(len(data)/settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': 1 if total_pages == 0 else total_pages, "current_page": 1 if page == 0 else page})

            record_start = (page-1) * items_per_page
            record_end = page * items_per_page
            data = data[record_start:record_end]

            return render(request, self.rr_review_table_template, {
                "objects": data,
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages
            })

    def get_umatched_bs_data(self, day, qry=""):
        """
        Method to get unmatched records comparing Blood Sample and Manifest records with Receipt
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
            INNER JOIN blood_sample_bloodsample as bs ON ( mr."CohortId" = bs."CohortId")
            WHERE mr."Barcode" not in (select "Barcode" from blood_sample_receiptrecords)
                    AND mr."CollectionDateTime" BETWEEN '{}' AND '{}'{}
            order by bs."CohortId";
            '''.format(day.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

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
        Method to get Unmatched records comparing Receipt with Blood Sample and Manifest records
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
            WHERE rr."Barcode" not in (SELECT
                                            "bs"."Barcode"
                                        FROM blood_sample_manifestrecords as mr
                                        INNER JOIN blood_sample_bloodsample as bs ON ( mr."CohortId" = bs."CohortId" )
                                    )
                    AND rr."DateTimeTaken" BETWEEN '{}' AND '{}'{}
            order by rr."Barcode";
            '''.format(day.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

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
            # Getting Unmatched records comparing Blood Sample and Manifest and Receipt records with Processed records
            if request.GET.get('State', ''):
                for key, value in state_status.items():
                    if value == request.GET.get('State'):
                        qry += f" AND bs.\"State\" = '{key}'"

            data = self.get_umatched_rr_data(day, qry)
            total_pages = math.ceil(len(data)/settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': 1 if total_pages == 0 else total_pages, "current_page": 1 if page == 0 else page})

            record_start = (page-1) * items_per_page
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
            # Getting Unmatched records comparing Processed records with Blood Sample and Manifest and Receipt records
            data = self.get_umatched_pr_data(day, "")
            total_pages = math.ceil(len(data)/settings.ITEMS_PER_PAGE)

            if total_pages < page:
                page = total_pages

            if request.GET.get('get_pages', 'False') == 'True':
                return JsonResponse({'status': 200, 'total_pages': 1 if total_pages == 0 else total_pages, "current_page": 1 if page == 0 else page})

            record_start = (page-1) * items_per_page
            record_end = page * items_per_page
            data = data[record_start:record_end]

            return render(request, self.pr_review_table_template, {
                "objects": data,
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages
            })

    def get_umatched_pr_data(self, day, qry=""):
        """
        Method to grt unmatched records comparing Processed records with Blood Sample and Manifest and Receipt records
        """
        query = '''
            SELECT "pr"."id",
                pr."ParentId",
                pr."Barcode",
                pr."ProcessedDateTime",
                pr."Volume",
                pr."NumberOfChildren",
                pr."Comments"
            FROM blood_sample_processedreport as pr
            WHERE pr."ParentId" not in (
                    SELECT
                        rr."SampleId"
                    FROM blood_sample_receiptrecords as rr
                    inner join blood_sample_manifestrecords as mr on rr."Barcode" = mr."Barcode"
                    inner join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
                ) AND pr."ProcessedDateTime" BETWEEN '{}' AND  '{}'{}
            order by pr."ParentId";
            '''.format(day.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

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
        Method to get unmatched records comparing Blood Sample and Manifest and Receipt records with Processed records
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
            inner join blood_sample_manifestrecords as mr on rr."Barcode"=mr."Barcode"
            inner join blood_sample_bloodsample as bs on bs."CohortId"=mr."CohortId"
            WHERE rr."SampleId" not in (SELECT
                                            "pr"."ParentId"
                                        FROM blood_sample_processedreport as pr
                                        join blood_sample_receiptrecords as rr on pr."ParentId"=rr."SampleId"
                                        join blood_sample_manifestrecords as mr on rr."Barcode"=mr."Barcode"
                                        join blood_sample_bloodsample as bs on bs."CohortId" = mr."CohortId"
                                    )
                    AND rr."ReceivedDateTime" BETWEEN '{}' AND '{}'{}
            order by bs."CohortId";
            '''.format(day.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                       day.replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"), qry)

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        return data


class EditBloodSampleView(LoginRequiredMixin, View):
    """
    Class for login functionality
    """
    blood_sample_review_template = 'review_blood_sample/blood-sample-edit.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the login form or redirect to Dashboard if session exists
        :param request: request object
        :return: HttpResponse object
        """
        return render(request, self.blood_sample_review_template, {
            "object": BloodSample.objects.get(id=int(request.GET.get('id'))),
            "STATECHOICE": dict(STATECHOICE)
        })

    def post(self, request, *args, **kwargs):
        object = BloodSample.objects.get(id=int(request.GET.get('id')))

        data_edit = request.GET.dict()
        data_edit = {key: data_edit[key]
                     for key in ['Comments', 'Barcode', 'State']}

        data_object = object.__dict__
        data_object = {key: data_object[key]
                       for key in ['Comments', 'Barcode', 'State']}
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]
        for i in diffs:
            setattr(object, i[0], i[1][1])
            BloodSampleChanges.objects.create(
                Field=i[0],
                FromValue=i[1][0],
                ChangedBy=request.user,
            )
        object.save()
        return JsonResponse({'status': 200, 'message': f'{request.GET.get("id")} sample updated successfully'})


class EditProcessedBsView(LoginRequiredMixin, View):
    """
    Class for editing Blood sample data in processed matched records review table
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
            "processed_object": ProcessedReport.objects.get(id=int(request.GET.get('processed_id'))),
            "STATECHOICE": dict(STATECHOICE)
        })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Blood sample data
        :param request: request object
        :return: HttpResponse object
        """
        object = BloodSample.objects.get(id=int(request.GET.get('id')))

        editable_fields = ['Comments', 'State']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_object = object.__dict__

        # Filter editable data from original blood sample object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the blood sample object and storing the info about changes in BloodSampleChanges
        for i in diffs:
            setattr(object, i[0], i[1][1])
            BloodSampleChanges.objects.create(
                Field=i[0],
                FromValue=i[1][0],
                ChangedBy=request.user,
            )
        object.save()

        return JsonResponse({'status': 200, 'message': f'{request.GET.get("id")} sample updated successfully'})


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
            "object": ManifestRecords.objects.get(id=int(request.GET.get('id'))),
            "rooms": sorted(Rooms, key=lambda L: (L.lower(), L)),
        })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Manifest data
        :param request: request object
        :return: HttpResponse object
        """
        object = ManifestRecords.objects.get(id=int(request.GET.get('id')))

        editable_fields = ['CohortId', 'Barcode',
                           'Room', 'Visit', 'Site', 'Comments']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_object = object.__dict__

        # Filter editable data from original mainfest object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the manifest object and storing the info about changes in ManifestChanges
        for i in diffs:
            setattr(object, i[0], i[1][1])
            ManifestChanges.objects.create(
                Field=i[0],
                FromValue=i[1][0],
                ChangedBy=request.user,
            )
        object.save()

        return JsonResponse({'status': 200, 'message': f'{request.GET.get("id")} manifest updated successfully'})


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
                "object": ReceiptRecords.objects.get(id=int(request.GET.get('id'))),
                "manifest_object": ManifestRecords.objects.get(id=int(request.GET.get('manifestid'))),
            })
        else:
            return render(request, self.receipt_edit_template, {
                "object": ReceiptRecords.objects.get(id=int(request.GET.get('id'))),
                "manifest_object": None
            })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Receipt data
        :param request: request object
        :return: HttpResponse object
        """
        object = ReceiptRecords.objects.get(id=int(request.GET.get('id')))

        editable_fields = ['Barcode', 'DateTimeTaken', 'Comments']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_object = object.__dict__

        # Filter editable data from original receipt object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the receipt object and storing the info about changes in ReceiptChanges
        for i in diffs:
            setattr(object, i[0], i[1][1])
            ReceiptChanges.objects.create(
                Field=i[0],
                FromValue=i[1][0],
                ChangedBy=request.user,
            )
        object.save()

        return JsonResponse({'status': 200, 'message': f'{request.GET.get("id")} receipt updated successfully'})


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
            "object": ProcessedReport.objects.get(id=int(request.GET.get('id'))),
        })

    def post(self, request, *args, **kwargs):
        """
        Method to update the Processed data
        :param request: request object
        :return: HttpResponse object
        """
        object = ProcessedReport.objects.get(id=int(request.GET.get('id')))

        editable_fields = ['ParentId', 'Comments']

        data_edit = request.GET.dict()

        # Filtering editable data inputs
        data_edit = {key: data_edit[key]
                     for key in editable_fields}

        data_object = object.__dict__

        # Filter editable data from original processed object
        data_object = {key: data_object[key]
                       for key in editable_fields}

        # Finding the fields that need to be updated
        diffs = [(k, (v, data_edit[k]))
                 for k, v in data_object.items() if v != data_edit[k]]

        # Updating the processed object and storing the info about changes in ProcessedReportChanges
        for i in diffs:
            setattr(object, i[0], i[1][1])
            ProcessedReportChanges.objects.create(
                Field=i[0],
                FromValue=i[1][0],
                ChangedBy=request.user,
            )
        object.save()
        return JsonResponse({'status': 200, 'message': f'{request.GET.get("id")} processed report updated successfully'})


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
        return JsonResponse({'status': 200,
                             'rooms': sorted(Rooms, key=lambda L: (L.lower(), L)),
                             })


class FinalStateChartView(LoginRequiredMixin, View):
    """
    Class for getting Final State Chart
    """

    def get(self, request, *args, **kwargs):
        """
        Method to get all the final state by days
        :param request: request object
        :return: HttpResponse object
        """
        query = '''
            SELECT
                DATE(bs."CreatedAt"),
                SUM (CASE
                        WHEN bs."State"='0' THEN 1
                    ELSE 0
                    END
                ) AS "State-0",
                SUM (
                    CASE
                    WHEN bs."State" = '1' THEN 1
                    ELSE 0
                    END
                ) AS "State-1",
                SUM (
                    CASE
                    WHEN bs."State" = '2' THEN 1
                    ELSE 0
                    END
                ) AS "State-2",
                SUM (
                    CASE
                    WHEN bs."State" = '3' THEN 1
                    ELSE 0
                    END
                ) AS "State-3",
                SUM (
                    CASE
                    WHEN bs."State" = '4' THEN 1
                    ELSE 0
                    END
                ) AS "State-4"
            FROM
                blood_sample_bloodsample as bs
            GROUP BY DATE(bs."CreatedAt") order by DATE(bs."CreatedAt")
        '''

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        # Formating the data
        dates = [i['date'] for i in data]
        data = [{
            "name": 'ACTIVE',
            "data": [i['State-0'] for i in data]
        }, {
            "name": 'UNABLE_TO_DRAW',
            "data": [i['State-1'] for i in data]
        }, {
            "name": 'UNABLE_TO_PROCESS',
            "data": [i['State-2'] for i in data]
        }, {
            "name": 'PROCESSED_ON_TIME',
            "data": [i['State-3'] for i in data]
        }, {
            "name": 'PROCESSED_NOT_ON_TIME',
            "data": [i['State-4'] for i in data]
        }]

        return JsonResponse({'status': 200, 'dates': dates, 'data': data, })


class NurseStatsChartView(LoginRequiredMixin, View):
    """
    Class for getting Stats about each Nurse
    """

    def get(self, request, *args, **kwargs):
        """
        Method to get percentage of accuracy with respect to each Nurse
        :param request: request object
        :return: HttpResponse object
        """
        query = '''
            SELECT
                bs."SiteNurseEmail" as x,
                round(cast(SUM (CASE
                    WHEN bs."State"='1' THEN 1
                    ELSE 0
                    END
                ) as decimal(7,2))/
                cast(count(bs."State") as decimal(100,2))*100, 2) as y,
                count(bs."State") as countData,
                SUM (CASE
                    WHEN bs."State"='1' THEN 1
                    ELSE 0
                    END
                ) as countUnabletodraw
            FROM
                blood_sample_bloodsample as bs
            GROUP BY bs."SiteNurseEmail" order by bs."SiteNurseEmail"
        '''

        with connection.cursor() as cursor:
            cursor.execute(query)
            nurse_day = [
                {'x': row[0].split('@')[0], 'y':float(
                    row[1]), 'countData':row[2], 'countUnabletodraw':row[3]}
                for row in cursor.fetchall()
            ]
        return JsonResponse({'status': 200, 'nurse_day': nurse_day, })


class UnresolvedChartView(LoginRequiredMixin, View):
    """
    Class for getting unresolved records by day wise
    """

    def get(self, request, *args, **kwargs):
        """
        Method to get the unresolved records by day wise
        :param request: request object
        :return: HttpResponse object
        """
        query = '''
            SELECT
                DATE(mr."CollectionDateTime"),
                SUM (CASE
                        WHEN mr."Site"='0' THEN 1
                    ELSE 0
                    END
                ) AS "FMH",
                SUM (CASE
                        WHEN mr."Site"='1' THEN 1
                    ELSE 0
                    END
                ) AS "KGH",
                SUM (CASE
                        WHEN mr."Site"='2' THEN 1
                    ELSE 0
                    END
                ) AS "Mile End Hospital",
                SUM (CASE
                        WHEN mr."Site"='3' THEN 1
                    ELSE 0
                    END
                ) AS "UCLH"
            FROM blood_sample_manifestrecords as mr
            LEFT JOIN blood_sample_bloodsample bs on "bs"."CohortId" = mr."CohortId"
            WHERE bs.id is null
            GROUP BY DATE(mr."CollectionDateTime") order by DATE(mr."CollectionDateTime")
        '''

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            site_data = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        # Formating the data
        site_dates = [i['date'] for i in site_data]
        site_data = [{
            "name": 'FMH',
            "data": [i['FMH'] for i in site_data]
        }, {
            "name": 'KGH',
            "data": [i['KGH'] for i in site_data]
        }, {
            "name": 'Mile End Hospital',
            "data": [i['Mile End Hospital'] for i in site_data]
        }, {
            "name": 'UCLH',
            "data": [i['UCLH'] for i in site_data]
        }]

        return JsonResponse({'status': 200, 'site_dates': site_dates, 'site_data': site_data, })


class ProcessedNotOnTimeView(LoginRequiredMixin, View):
    """
    Class for getting records that are not processed on time with day wise
    """

    def get(self, request, *args, **kwargs):
        """
        Method to get the records that are not processed on time with day wise
        :param request: request object
        :return: HttpResponse object
        """
        query = '''
            SELECT
                DATE(bs."CreatedAt"),
                count(1)
            FROM
                blood_sample_bloodsample as bs
            WHERE now() - '36 hour'::interval > bs."CreatedAt" AND bs."State" in ('0','4')
            GROUP BY DATE(bs."CreatedAt") order by DATE(bs."CreatedAt")
        '''

        with connection.cursor() as cursor:
            cursor.execute(query)
            processed_not_ontime = [
                [row[0], row[1]]
                for row in cursor.fetchall() if row[1]
            ]

        return JsonResponse(
            {
                'status': 200,
                'processed_not_ontime': processed_not_ontime,
                'processed_hours': settings.PROCESSING_HOURS,
            }
        )
