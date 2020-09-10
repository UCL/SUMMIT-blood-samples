
import math
from datetime import datetime
import datetime
import time

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import get_template
from django.views import View

from manage_users.models import *
import dateutil.relativedelta
from .models import *

from .choices_data import \
    state_status, \
    site_choices, \
    visit_choices, \
    processing_status, \
    sample_type, \
    site_held_choices


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
            # if request params doesn't have settings key,
            # assign default values to settings option
            settings_options = dict(BS=request_data['BloodSample'],
                                    MR=request_data['Manifest'],
                                    RR=request_data['Receipt'],
                                    PR=request_data['Processed'])
            for table, columns in settings_options.items():
                for column in columns:
                    settings_options[table] = column.split(',')
        else:
            # if exists converting string type to dictionary type using
            # eval keyword
            settings_options = eval(request_data['settings'][0])

        if 'filters' not in request_data:
            # if request params doesn't have filters key, assign default
            # values to filters option
            filter_options = dict(DF=request_data['DateFrom'],
                                  DT=request_data['DateTo'],
                                  Site=request_data['Site'],
                                  Room=request_data['Room'],
                                  Visit=request_data['Visit'],
                                  State=request_data['State'])
        else:
            # if exists converting string type to dictionary type using
            # eval keyword
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

        # generating a raw sql query based on filters and settings
        # options as requested by user
        query = """ SELECT """
        headers = []

        # selecting the required columns selected by the user
        for table, columns in settings_options.items():
            for column in columns:
                if column != '':
                    # headers for columns in download tab that
                    #  needs to be displayed
                    headers.append(column)
                if table == 'BS' and column != '':
                    query += "bs.\"" + column + "\", "
                if table == 'MR' and column != '':
                    query += "mr.\"" + column + "\", "
                if table == 'RR' and column != '':
                    query += "rr.\"" + column + "\", "
                if table == 'PR' and column != '':
                    query += "pr.\"" + column + "\", "

        query = query[:-2]
        query += """from blood_sample_processedreport as pr
                    right join blood_sample_receiptrecords as rr on \
                        pr."ParentId" = rr."SampleId"
                    right join blood_sample_manifestrecords as mr on \
                        rr."Barcode" = mr."Barcode"
                    right join blood_sample_bloodsample as bs on \
                        bs."CohortId" = mr."CohortId"
                """
        extra = ' WHERE '
        date_start = filter_options['DF'][0]
        date_end = filter_options['DT'][0]

        # if no date-from and date -to is not mentioned assigning default
        #  values of 1900-01-01, present day by default
        if date_end == '':
            date_end = datetime.datetime.now().strftime("%Y-%m-%d")
            filter_options['DT'][0] = date_end

        if date_start == '':
            last_month = datetime.datetime.strptime(
                date_end, "%Y-%m-%d") - \
                    dateutil.relativedelta.relativedelta(months=1)
            date_start = last_month.strftime("%Y-%m-%d")
            filter_options['DF'][0] = date_start

        date_end = datetime.datetime.strptime(
            date_end, "%Y-%m-%d") + datetime.timedelta(days=1)
        date_end = date_end.strftime("%Y-%m-%d")

        # adding filtered values as requested by user
        for filt, value in filter_options.items():
            if filt == 'Site' and value[0] != '':
                val = list(site_choices.keys())[
                    list(site_choices.values()).index(value[0])]
                extra += "mr.\"Site\"='" + val + "' AND "

            if filt == 'Room' and value[0] != '':
                extra += "mr.\"Room\"='" + value[0] + "' AND "

            if filt == 'Visit' and value[0] != '':
                val = list(visit_choices.keys())[
                    list(visit_choices.values()).index(value[0])]
                extra += "mr.\"Visit\"='" + val + "' AND "

            if filt == 'State' and value[0] != '':
                val = list(state_status.keys())[
                    list(state_status.values()).index(value[0])]
                extra += "bs.\"State\"='" + val + "' AND "

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
        # total pages calculation based on items per page as
        # mentioned in settings
        total_pages = math.ceil(len(data) / items_per_page)
        # records based on page to display
        record_start = (page - 1) * items_per_page
        record_end = page * items_per_page

        if csv:
            items_per_page = len(data)

        # updating the data of enum field with respective data
        if 'State' in settings_options['BS'] or \
            'Site' in settings_options['MR'] or \
                'Visit' in settings_options['MR'] or \
                    'SiteHeld' in settings_options['PR']:
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
            try:
                ind_site_held = headers.index('SiteHeld')
                site_held_status = True
            except:
                site_held_status = False

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
                if site_held_status and data[row][ind_site_held] is not None:
                    data[row][ind_site_held] = site_held_choices[data[row][ind_site_held]]
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
            'SiteHeld':'Site held',
            'id': 'Id',
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
            filename = 'BloodSamples_' + \
                datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.csv'
            content = "attachment; filename=%s" % (filename)
            response['Content-Disposition'] = content
            # response of content that needs to be returned if csv download
            response.write(template.render(download_context))

            return response

        # if more than 1 page will return the data based on the
        # items and page number
        if table == "True":
            return render(request, self.download_blood_table_template, {
                "objects": [headers] + data[record_start:record_end],
                "current_page": 1 if page == 0 else page,
                "total_pages": 1 if total_pages == 0 else total_pages,
                'db_data': data,
                'bs_len': bs_len,
                'mr_len': mr_len, 'rr_len': rr_len,
                'pr_len': pr_len,
                'settings': settings_options,
                'filters': filter_options
            })

        # for page 1 display
        context = {
            "current_page": 1 if page == 0 else page,
            "total_pages": 1 if total_pages == 0 else total_pages,
            'db_data': data,
            'bs_len': bs_len, 'mr_len': mr_len, 'rr_len': rr_len,
            'pr_len': pr_len,
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
            'ParentID', 'SampleType', 'Volume', 'VolumeUnit',
            'PostProcessingStatus', 'AliquotId').order_by('ParentID', 'SampleType')
        aliquots_data = list(aliquots_data)

        # updating the enum fields w.r.t values
        for row in range(len(aliquots_data)):
            aliquots_data[row] = list(aliquots_data[row])
            aliquots_data[row][4] = processing_status[aliquots_data[row][4]]
            aliquots_data[row][1] = sample_type[aliquots_data[row][1]]
            aliquots_data[row] = tuple(aliquots_data[row])

        # if no data to display updating the data
        if len(aliquots_data) == 0:
            aliquots_data = 'No Records to Display'

        headers = ('Parent id', 'Sample type', 'Volume',
                   'Volume unit', 'Post processing status','Aliquot Id')

        # if csv download is True it works on download
        if csv and len(aliquots_data) != 0:
            response = HttpResponse(content_type='csv')
            aliquots_data.insert(0, headers)
            template = get_template('csv_download.txt')
            csv_data = aliquots_data
            csv_content = {
                'data': csv_data,
            }
            filename = 'Aliquots_' + \
                datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.csv'
            content = "attachment; filename=%s" % (filename)
            response['Content-Disposition'] = content
            response.write(template.render(csv_content))

            return response

        # setting page number to 1 as default
        page = int(request.GET.get('page', 1))
        # if page 1 setting table to false
        table = request.GET.get('table', 'False')
        # calculating total num of pages
        total_pages = math.ceil(len(aliquots_data) / settings.ITEMS_PER_PAGE)
        # items per page
        items_per_page = settings.ITEMS_PER_PAGE
        # data presentation based on page number
        record_start = (page - 1) * items_per_page
        record_end = page * items_per_page

        # if page more than 1 setting the data in page based on number
        if table == "True":
            return render(request, self.aliquots_table, {
                "objects": [headers] + aliquots_data[record_start:record_end],
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

        # receiving data based on the existing
        # visit, room and site dynamically
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

