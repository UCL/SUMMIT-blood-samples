import re
from datetime import datetime
import datetime
import time
import pandas as pd
import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.timezone import make_aware
from django.views import View

from manage_users.models import *
from .models import *
from .choices_data import site_choices, sample_type, site_held_choices, visit_choices

# Get an instance of a logger
logger = logging.getLogger(__name__)


class UploadView(LoginRequiredMixin, View):
    """
    Class for upload functionality
    """

    template_name = 'upload.html'

    def get(self, request, *args, **kwargs):
        """
        Method to get the upload view and stats of uploaded samples
        in a given day
        :param request: request object
        :return: HttpResponse object
        """
        day, days = self.get_dayformated_and_days(request)

        # Disabling the feature dates
        shownextday = datetime.datetime.today().strftime(
            '%d%b%y') in [i.strftime('%d%b%y') for i in days]

        # Getting Blood Samples records count in a given day by
        # CreatedAt field
        blood_samples_loaded = BloodSample.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0,
                                          second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))

        # Getting Blood Samples records count in a given day by Files imported
        blood_samples_imported = BloodSampleImport.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0,
                                          second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        blood_samples_imported_cnt = BloodSample.objects.filter(
            ImportId__in=blood_samples_imported.
            values_list('id', flat=True)[::1]).count()

        # Checking if Last uploaded blood sample file is reviewed or not
        try:
            reviewed = blood_samples_imported.last().Reviewed
        except:
            reviewed = False

        # Getting Manifest records count in a given day by
        # CollectionDateTime field
        manifest_loaded = ManifestRecords.objects.filter(
            CollectionDateTime__range=(day.replace(hour=0, minute=0,
                                                   second=0, microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))

        # Getting Manifest records count in a given day by Files imported
        manifest_imported = ManifestImports.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0,
                                          microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        no_of_files_uploaded = manifest_imported.count()
        manifest_imported_cnt = ManifestRecords.objects.filter(
            ImportId__in=manifest_imported.values_list('id', flat=True)[::1])\
            .count()

        # Getting Receipt records count in a given day by DateTimeTaken field
        receipt_loaded = ReceiptRecords.objects.filter(
            DateTimeTaken__range=(day.replace(hour=0, minute=0, second=0,
                                              microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))

        # Getting Receipt records count in a given day by Files imported
        receipt_imported = ReceiptImports.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0,
                                          microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        receipt_imported_cnt = ReceiptRecords.objects.filter(
            ImportId__in=receipt_imported.values_list('id', flat=True)[::1])\
            .count()

        # Getting Receipt records count in a given day by DateTimeTaken field
        processed_loaded = ProcessedReport.objects.filter(
            ProcessedDateTime__range=(day.replace(hour=0, minute=0, second=0,
                                              microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))

        # Getting Processed records count in a given day by Files imported
        processed_imported = ProcessedImports.objects.filter(
            CreatedAt__range=(day.replace(hour=0, minute=0, second=0,
                                          microsecond=0), day.replace(
                hour=23, minute=59, second=59, microsecond=0)))
        processed_imported_cnt = ProcessedReport.objects.filter(
            ImportId__in=processed_imported.values_list('id', flat=True)[::1])\
            .count()

        return render(request, self.template_name, {
            "days": days,
            "blood_samples_cnt": blood_samples_loaded.count(),
            "blood_samples_imported": blood_samples_imported_cnt,
            'manifest_imported': manifest_imported_cnt,
            'manifest_loaded_count': manifest_loaded.count(),
            'receipt_imported': receipt_imported_cnt,
            "receipt_loaded_cnt": receipt_loaded.count(),
            'processed_imported': processed_imported_cnt,
            'processed_loaded':processed_loaded.count(),
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
                day[0].split(' ')[0][:3] + ' ' + day[0].split(' ')[1] +
                ',' + day[1], '%b %d, %Y')
            days = [(day - datetime.timedelta(days=x))
                    for x in range(4)]
            days.reverse()
        elif 'next' in request.GET.get('day', ''):
            day = request.GET.get('day')
            day = day.split('-')[1].split(',')
            day = datetime.datetime.strptime(
                day[0].split(' ')[0][:3] + ' ' + day[0].split(' ')[1] +
                ',' + day[1], '%b %d, %Y')
            days = [(day + datetime.timedelta(days=x))
                    for x in range(4)]

            # Updating the days if future days are present
            try:
                if days.index(datetime.datetime.today().replace(hour=0,
                                                                minute=0, second=0, microsecond=0)) in [0, 1, 2]:
                    days = [(datetime.datetime.today() -
                             datetime.timedelta(days=x))
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
                    firstday[0].split(' ')[0][:3] + ' ' +
                    firstday[0].split(' ')[1] + ',' + firstday[1], '%b %d, %Y')
                days = [(firstday - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()
                current_day = day.split('-')[2]
                current_day = current_day.split(',')
                day = datetime.datetime.strptime(
                    current_day[0].split(' ')[0][:3] + ' ' +
                    current_day[0].split(' ')[1] + ',' +
                    current_day[1], '%b %d, %Y')
            else:
                day = day.split(',')
                day = datetime.datetime.strptime(
                    day[0].split(' ')[0][:3] + ' ' + day[0].split(' ')[1] +
                    ',' + day[1], '%b %d, %Y')
                days = [(day - datetime.timedelta(days=x))
                        for x in range(4)]
                days.reverse()
        return make_aware(day), days


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
        df = pd.read_csv(blood_sample_file, na_filter=False)

        # Dropping duplicates in the file
        df = df.drop_duplicates()

        # Validations
        # Columns validation
        if not set(
            ['Id', 'CohortId', 'AppointmentId', 'Barcode', 'User', 'CreatedAt']
        ).issubset(df.columns):
            return JsonResponse({
                'status': 412,
                'message': 'Column names not matching'
            })

        # Input Records Count Validations i.e., Uploaded file should have more
        # number of record compared to database
        if BloodSample.objects.count() >= df.shape[0]:
            return JsonResponse({
                'status': 412,
                'message': 'The uploaded file has less than or equal \
                    number of records compared to database records'
            })

        # Checking no duplicatesId columns
        if df.duplicated(subset=['Id']).any():
            return JsonResponse({
                'status': 412,
                'message': 'Id column has duplicates'
            })

        # CreatedAt column validation
        try:
            df['CreatedAt'] =pd.to_datetime(df['CreatedAt'])
        except:
            return JsonResponse({
                'status': 412,
                'message': 'CreatedAt column values are not \
                    in expected format'})

        # Getting stats of newly uploading file
        report_ids = BloodSample.objects.values_list('id', flat=True)[
            ::1]
        excel_ids = df.Id.values.tolist()
        new_records = list(set(excel_ids).difference(report_ids))

        # get how many records for this day


        if request.GET.get('confirm', '') == 'True':
            # Dropping duplicates when compared to database
            df = df[df['Id'].isin(new_records)]

            # Storing file to uploads folder
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT + '/CurrentAppointmentBlood')

            try:
                filename = fs.save(blood_sample_file.name.split(
                    '.')[0] + time.strftime("%d%m%Y-%H%M%S") + '.' +
                    blood_sample_file.name.split('.')[1], blood_sample_file)
            except Exception as e:
                logger.error(f'Something went wrong in storing Blood Sample \
                    file in Uploads folder - {e}')
                return None
            # End of storing file

            day, days = UploadView.get_dayformated_and_days(self, request)

            # Uploading file details to BloodSampleImport table
            try:
                ImportId = BloodSampleImport.objects.create(
                    FilePath="CurrentAppointmentBlood/" + filename,
                    OriginalFileName=blood_sample_file.name,
                    CreatedBy=request.user,
                    CreatedAt=day,
                    Deleted=False,
                    Reviewed=False,
                )
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Blood Sample file details in imports table - {e}')
                return None

            # Bulk uploading to BloodSample table
            try:


                model_instances = [
                    BloodSample(
                        id=record['Id'],
                        CohortId=record['CohortId'],
                        Barcode=record['Barcode'] if re.match(
                            r"^(E[0-9]{6})+$", record['Barcode']) else "",
                        Comments="" if re.match(
                            r"^(E[0-9]{6})+$", record['Barcode'])
                        else record['Barcode'],
                        AppointmentId=record['AppointmentId'],
                        SiteNurseEmail=record['User'],
                        ImportId=ImportId,
                        CreatedAt=record['CreatedAt'],
                        State=0 if (re.match(r"^(E[0-9]{6})", record['Barcode']) is not None) |
                                   (re.match(r"^(K[0-9]{6})", record['Barcode']) is not None)
                                else 1,
                    ) for index, record in df.iterrows()
                ]

                BloodSample.objects.bulk_create(model_instances)
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Blood Sample file data - {e}')
                return None

            return render(request, self.blood_sample_success_template, {
                "new_records": len(new_records)
            })

        return render(request, self.blood_sample_confirm_template, {
            "new_records": len(new_records)
        })


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
        return render(request, self.template_name, {'visit_choices': visit_choices})

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
        if (df.iloc[2, 3] != 'Room No.') | \
            (df.iloc[2, 1] != 'Site') | \
            (df.iloc[4, 1] != 'Barcode ID') | \
            (df.iloc[4, 2] != 'Collection Date & Time') | \
            (df.iloc[4, 3] != 'Cohort ID') | \
            (df.iloc[4, 4] != 'Visit'):
            return JsonResponse({
                'status': 412,
                'message': 'Column names not matching'
            })

        # Getting room value from file
        room = int(df.iloc[2, 4]) if isinstance(
            df.iloc[2, 4], float) else df.iloc[2, 4]

        # Getting site value from file and validating it
        site = df.iloc[2, 2]
        if site not in ['FMH', 'KGH', 'MEH', 'UCLH']:
            return JsonResponse({'status': 412, 'message': 'Invalid Site'})

        # Dropping rows where all the columns are empty if any exists
        df = df.iloc[5:-1, 1:].dropna()

        # Check for empty Manifest file
        if df.shape[0] == 0:
            return JsonResponse({
                'status' : 412,
                'message' : 'Unable to load, empty file'
            })

        # Dropping duplicates in the file
        df = df.drop_duplicates()

        df.columns = ['Barcode', 'CollectionDateTime', 'CohortId', 'Visit']

        # Validating CollectionDateTime column
        if True in (df['CollectionDateTime'].map(type) !=
                    datetime.datetime).tolist():
            return JsonResponse({
                'status': 412,
                'message': 'CollectionDateTime column values are not \
                    in expected format'
            })


        # move day and days up so have reference
        day, days = UploadView.get_dayformated_and_days(self, request)

        # which is needed to valid that the dates in the manifest
        # correspond to the date being uploaded to
        if False in (df['CollectionDateTime'].apply(
            lambda d: True if d.date() == day.date() else False
            ).tolist()):

            return JsonResponse({
                'status' : 412,
                'message' : f'Error: All collection dates must refer to the upload date, {day.date()}'
            })

        # Validating removing extra space if any in CohortId column
        df['CohortId'] = df['CohortId'].apply(lambda x: x.strip())

        # Validating CohortId value length
        if False in (df['CohortId'].str.match(r'^([0-9]{3})-([A-Z]{3})$').tolist()):
            return JsonResponse({
                'status': 412,
                'message': 'CohortId column values are \
                    not in expected format ###-AAA'})

        # Validating Barcode format
        if False in (df['Barcode'].str.match(r'^E([0-9]{6})$').tolist()):
            return JsonResponse({
                'status': 412,
                'message': 'Error: Barcode column values are \
                    not in expected format E######'})

        # Validating Visit
        if False in df['Visit'].isin([v for (k,v) in visit_choices.items()]).tolist():

            return JsonResponse({
                'status' : 412,
                'message' : 'Error: Visit has invalid value.'
            })


        # Getting stats of uploaded file
        manifest_db_df = pd.DataFrame(
            list(ManifestRecords.objects.
                 values('Barcode', 'CollectionDateTime', 'CohortId', 'Visit')))

        blood_sample_cohort = BloodSample.objects.\
            values_list('Barcode', flat=True)[::1]
        df_cohort = df['Barcode'].tolist()

        # Records count that are not found in blood samples table
        record_not_found_cnt = len(
            set(df_cohort).difference(blood_sample_cohort))
        duplicates_cnt = 0

        # Records count that are found in blood samples table
        record_found_cnt = len(df_cohort) - record_not_found_cnt

        unique_df = df

        if not manifest_db_df.shape == (0, 0):
            # Dropping duplicates in the file comparing with the
            # manifest table records
            manifest_db_df['key'] = manifest_db_df.Barcode.str.cat(manifest_db_df.Barcode,sep='_')
            df['key'] = df.Barcode.str.cat(df.Barcode,sep='_')
            unique_df = df[~df.key.isin(manifest_db_df.key)]

            # Getting duplicated count comparing with the database
            duplicates_cnt = df.shape[0] - unique_df.shape[0]

        if request.GET.get('confirm', '') == 'True':
            # Storing file to the uploads folder
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT + '/Manifests')

            try:
                filename = fs.save(manifest_file.name.split(
                    '.')[0] + time.strftime("%d%m%Y-%H%M%S") + '.' +
                    manifest_file.name.split('.')[1], manifest_file)
            except Exception as e:
                logger.error(f'Something went wrong in storing Manifest \
                    file in Uploads folder - {e}')
                return JsonResponse({
                    'status': 500,
                    'message': f'Failed to store Manifest file in uploads folder: {e}'
                })
            # End of storing file

            # Uploading file details to ManifestImports table
            try:
                ImportId = ManifestImports.objects.create(
                    FilePath="Manifests/" + filename,
                    OriginalFileName=manifest_file.name,
                    CreatedBy=request.user,
                    CreatedAt=day,
                    Deleted=False
                )
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Manifest file details in imports table - {e}')
                return JsonResponse({
                    'status': 500,
                    'message': f'Failed to create manifest record in DB: {e}'
                })

            # Bulk uploading to ManifestRecords table
            try:
                model_instances = [
                    ManifestRecords(
                        Visit=dict((v, k)
                                  for k, v in visit_choices.items()).get(record[3]),
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
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Manifest file data - {e}')
                return JsonResponse({
                    'status': 500,
                    'message': f'Failed to create manifest records in DB: {e}'
                })

            return render(request, self.blood_sample_success_template, {
                "duplicates_cnt": duplicates_cnt,
                "record_not_found_cnt": record_not_found_cnt,
                "record_found_cnt": record_found_cnt,
            })

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
        if not set(['ParticipantID', 'Clinic', 'Date Time Taken',
                    'TubeBarcode',
                    'TubeType', 'LoggedInTime', 'Volume',
                    'VolUnit',
                    'Condition']).issubset(df.columns):
            return JsonResponse({
                'status': 412,
                'message': 'Column names not matching'
            })

        # Validating DateTime Taken column
        try:
            df['Date Time Taken'] = df['Date Time Taken'].\
                apply(lambda x: datetime.datetime.strptime(
                    x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({
                'status': 412,
                'message': 'DateTime Taken column values are not in \
                    expected format'})

        # Validating Received DateTime column
        try:
            df['LoggedInTime'] = df['LoggedInTime'].\
                apply(lambda x: datetime.datetime.strptime(
                    x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({
                'status': 412,
                'message': 'Received DateTime column values are not in \
                    expected format'})

        # Validating Volume Unit column
        if True in (df['VolUnit'].str.lower() != 'ul').tolist():
            return JsonResponse({
                'status': 412,
                'message': 'Volume Unit column values are not an uL'
            })

        # Validating Tissue sub-type column
        if True in (df['TubeType'] != 'EDTA').tolist():
            return JsonResponse({
                'status': 412,
                'message': 'Tissue sub-type column values are not an EDTA'
            })

        # Validating and converting Clinic column
        clinic_mapping = {
            'finchley memorial hospital': 0,
            'king george hospital': 1,
            'mile end hospital': 2,
            'university college london hospital': 3,
            'uk biocentre signature': 4
        }
        try:
            df['Clinic'] = df['Clinic'].apply(
                lambda x:
                    clinic_mapping[x.lower()])
        except:
            return JsonResponse({
                'status': 412,
                'message': 'Clinic column values are not in expected format'
            })

        # Getting stats of the uploaded file
        df['DateTime Taken compare'] = df['Date Time Taken'].apply(
            lambda x: x.strftime('%d/%m/%Y %H:%M'))
        manifest_db_df = pd.DataFrame(ManifestRecords.objects.all().values())
        manifest_db_df['CollectionDateTime'] = \
            manifest_db_df['CollectionDateTime'].apply(
            lambda x: x.strftime('%d/%m/%Y %H:%M'))
        manifest_db_filtered = manifest_db_df[manifest_db_df['CohortId'].
                                              isin(BloodSample.objects.values_list(
                                                  'CohortId', flat=True)[::1])]

        # Getting records already present in the database
        manifest_match = df[df['ParticipantID'].isin(
            manifest_db_filtered.Barcode.values) & df['Clinic'].isin(
            manifest_db_filtered.Site.values) &
            df['DateTime Taken compare'].isin(
            manifest_db_filtered.CollectionDateTime.values)]
        record_found_cnt = manifest_match.shape[0]

        # Getting records where there is mismatch on manifest site
        # with uploaded receipt Clinic
        mismatch_site = df[df['ParticipantID'].isin(
            manifest_db_df.Barcode.values) & ~df['Clinic'].isin(
            manifest_db_df.Site.values)]
        mismatch_site_found_cnt = mismatch_site.shape[0]

        # Getting records where there is mismatch on Receipt
        # DateTime Taken with Manifest CollectionDateTime
        mismatch_blood_draw = df[df['ParticipantID'].isin(
            manifest_db_df.Barcode.values) &
            ~df['DateTime Taken compare'].isin(
            manifest_db_df.CollectionDateTime.values)]
        mismatch_blood_draw_found_cnt = mismatch_blood_draw.shape[0]

        # Checking number of Receipt records barcodes not existing in
        # Manifest table
        receipt_barcode_existance = df[~df['ParticipantID'].isin(
            manifest_db_df.Barcode.values)].shape[0]

        # Getting total records
        total_records = df.shape[0]

        if request.GET.get('confirm', '') == 'True':
            del df['DateTime Taken compare']

            # storing file
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT + '/Receipt')

            try:
                filename = fs.save(receipt_file.name.split(
                    '.')[0] + time.strftime("%d%m%Y-%H%M%S") + '.' +
                    receipt_file.name.split('.')[1], receipt_file)
            except Exception as e:
                logger.error(f'Something went wrong in storing Receipt \
                    file in Uploads folder - {e}')
                return None
            # End of storing file

            day, days = UploadView.get_dayformated_and_days(self, request)

            # Uploading file details to ReceiptImports table
            try:
                ImportId = ReceiptImports.objects.create(
                    FilePath="Receipt/" + filename,
                    OriginalFileName=receipt_file.name,
                    CreatedBy=request.user,
                    CreatedAt=day,
                    Deleted=False
                )
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Receipt file details in imports table - {e}')
                return None

            # Dropping duplicates in file comparing with ReceiptRecords table
            receipt_barcode = ReceiptRecords.objects.\
                values_list('Barcode', flat=True)[
                    ::1]
            df = df[~df['ParticipantID'].isin(receipt_barcode)]

            # Bulk uploading to ReceiptRecords table
            try:
                model_instances = [
                    ReceiptRecords(
                        Barcode=record['ParticipantID'],
                        Clinic=record['Clinic'],
                        DateTimeTaken=make_aware(record['Date Time Taken']),
                        SampleId=record['TubeBarcode'],
                        TissueSubType=record['TubeType'],
                        ReceivedDateTime=make_aware(
                            record['LoggedInTime']),
                        Volume=record['Volume'],
                        VolumeUnit=record['VolUnit'],
                        Condition=record['Condition'],
                        ImportId=ImportId,
                    ) for index, record in df.iterrows()
                ]
                ReceiptRecords.objects.bulk_create(model_instances)
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Receipt file data - {e}')
                return None

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
        return render(request, self.template_name, {'site_held_choices': site_held_choices})

    def post(self, request, *args, **kwargs):
        """
        Method to upload the Processed
        :param request: request object
        :return: HttpResponse object
        """
        processed_file = request.FILES.get(u'file')
        siteheld = request.POST.get('siteheld', '0')

        # Converting input file to data frame
        df = pd.read_csv(processed_file)

        # Dropping duplicates in the file
        df = df.drop_duplicates()

        # Validations

        # File validation
        if not set(['Participant ID', 'Parent ID', 'Sample ID',
                    'Tissue Sub-Type',
                    'Sample Type', 'Received Date Time',
                    'Processed Date Time', 'Volume',
                    'Volume Unit']).issubset(df.columns):
            return JsonResponse({
                'status': 412,
                'message': 'Column names not matching'
            })

        # Validating Sample Type column
        if set(df['Sample Type'].unique().tolist()) != \
                set(['RBC', 'Plasma', 'BuffyCoat']):
            return JsonResponse({
                'status': 412,
                'message': 'Sample Type column values are not having \
                    expected values'})

        # splitting processed and aliquots from the file
        #parent_df = df[df['Parent ID'] == 'No Parent']
        parent_df = df.groupby(['Participant ID']).agg({'Parent ID': 'first',
                                                        'Received Date Time' : 'first',
                                                        'Processed Date Time' : 'first',
                                                        'Volume' : 'sum',
                                                        'Tissue Sub-Type' : 'count'})

        # reset index pushing 'Participant ID as a column name
        parent_df.reset_index(inplace=True)

        # add missing columns
        parent_df['Sample ID'] = parent_df['Parent ID']
        parent_df['Parent ID'] = 'No Parent'
        parent_df['No. of Children'] = parent_df['Tissue Sub-Type']
        parent_df['Tissue Sub-Type'] = 'EDTA'
        parent_df['Sample Type'] = 'Whole Blood'
        parent_df['Volume Unit'] = 'ul'


        # change in format need to create the parent by aggregating the chld
        child_df = df

        # Validating Processed Date Time column
        try:
            parent_df['Processed Date Time'].apply(
                lambda x: datetime.datetime.strptime(
                    x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({
                'status': 412,
                'message': 'Processed Date Time column values are not in \
                    expected format'})

        # Validating Received Date Time column
        try:
            parent_df['Received Date Time'].apply(
                lambda x: datetime.datetime.strptime(
                    x, "%d/%m/%Y %H:%M"))
        except:
            return JsonResponse({
                'status': 412,
                'message': 'Received DateTime column values are not in \
                    expected format'})

        # Validating Volume Unit column
        if True in (parent_df['Volume Unit'].str.lower() != 'ul').tolist():
            return JsonResponse({
                'status': 412,
                'message': 'Volume Unit column with Parent ID, \
                    values are not an uL'})

        if True in (df[df['Parent ID'] !=
                       'No Parent']['Volume Unit'].str.lower() != 'ul').tolist():
            return JsonResponse({
                'status': 412,
                'message': 'Volume Unit column with no Parent ID, \
                    values are not an ul'})

        # Validating Sample Type column
        if True in (parent_df['Sample Type'] != 'Whole Blood').tolist():
            return JsonResponse({
                'status': 412,
                'message': 'Sample Type column with Parent ID, \
                    values are not an Whole Blood'})

        if set(df[df['Parent ID'] != 'No Parent']
               ['Sample Type'].unique().tolist()) != \
                set(['RBC', 'Plasma', 'BuffyCoat']):
            return JsonResponse({
                'status': 412,
                'message': 'Sample Type column with no Parent ID, \
                    values are not having expected values'})

        # Validating Tissue Sub-Type column
        if True in (df['Tissue Sub-Type'] != 'EDTA').tolist():
            return JsonResponse({
                'status': 412,
                'message': 'Tissue sub-type column values are not an EDTA'})

        # # Validating No. of Children column
        # if True in (df['No. of Children'].map(type) != int).tolist():
        #     return JsonResponse({
        #         'status': 412,
        #         'message': 'No. of Children column values are not \
        #             having expected values'})

        # Validating Volume column
        if True in (df['Volume'].map(type) != int).tolist():
            return JsonResponse({
                'status': 412, 'message': 'Volume column values are not \
                    having expected values'})

        # Getting stats of the uploaded file
        total_records = parent_df.shape[0]

        manifest_db_df = pd.DataFrame(ManifestRecords.objects.filter(
            Barcode__in=parent_df['Participant ID'].tolist()).values())

        # Checking number of Parent records barcodes not existing in
        # Manifest table
        receipt_barcode_existance = total_records - manifest_db_df.shape[0]

        # Getting records that are processed outside of 36 hrs
        manifest_parent_df = parent_df[parent_df['Participant ID'].isin(
            manifest_db_df.Barcode.values)]
        manifest_db_df = manifest_db_df.rename(
            columns={'Barcode': 'Participant ID'})
        manifest_db_df = pd.merge(
            manifest_parent_df, manifest_db_df, on='Participant ID')
        manifest_db_df['Processed Date Time'] = \
            manifest_db_df['Processed Date Time'].apply(
                lambda x: datetime.datetime.strptime(
                    x, "%d/%m/%Y %H:%M"))
        manifest_db_df['CollectionDateTime'] = \
            manifest_db_df['CollectionDateTime'].apply(
                lambda x: datetime.datetime.strftime(
                    x, "%d/%m/%Y %H:%M"))
        manifest_db_df['CollectionDateTime'] = \
            manifest_db_df['CollectionDateTime'].apply(
                lambda x: datetime.datetime.strptime(
                    x, "%d/%m/%Y %H:%M"))

        manifest_db_df['greaterthan_36hrs'] = ''
        for index, row in manifest_db_df.iterrows():
            manifest_db_df.at[index, 'greaterthan_36hrs'] = True if (
                manifest_db_df['Processed Date Time'].iloc[index] -
                manifest_db_df['CollectionDateTime'].iloc[index]).\
                total_seconds() // (settings.PROCESSING_HOURS * 100) \
                > settings.PROCESSING_HOURS else False

        if request.GET.get('confirm', '') == 'True':
            # storing file
            fs = FileSystemStorage(
                location=settings.UPLOAD_ROOT + '/Processed')

            try:
                filename = fs.save(processed_file.name.split(
                    '.')[0] + time.strftime("%d%m%Y-%H%M%S") + '.' +
                    processed_file.name.split('.')[1], processed_file)
            except Exception as e:
                logger.error(f'Something went wrong in storing Processed \
                    file in Uploads folder - {e}')
                return None
            # End of storing file

            day, days = UploadView.get_dayformated_and_days(self, request)

            # Uploading file details to ProcessedImports table
            try:
                ImportId = ProcessedImports.objects.create(
                    FilePath="Processed/" + filename,
                    OriginalFileName=processed_file.name,
                    CreatedBy=request.user,
                    CreatedAt=day,
                    Deleted=False
                )
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Processed file details in imports table - {e}')
                return None

            # Dropping duplicates in file comparing with ProcessedReport table
            processed_barcode = ProcessedReport.objects.\
                values_list('Barcode', flat=True)[
                    ::1]
            parent_df = parent_df[~parent_df['Participant ID'].isin(
                processed_barcode)]

            parent_df['Processed Date Time'] = \
                parent_df['Processed Date Time'].apply(
                lambda x: datetime.datetime.strptime(x, "%d/%m/%Y %H:%M"))
            parent_df['Received Date Time'] = \
                parent_df['Received Date Time'].apply(
                lambda x: datetime.datetime.strptime(x, "%d/%m/%Y %H:%M"))

            # Bulk uploading to ProcessedReport table
            try:
                model_instances = [
                    ProcessedReport(
                        Barcode=record['Participant ID'],
                        ParentId=ReceiptRecords.objects.filter(
                            Barcode=record['Participant ID']).first().SampleId,
                        TissueSubType=record['Tissue Sub-Type'],
                        ReceivedDateTime=make_aware(
                            record['Received Date Time']),
                        ProcessedDateTime=make_aware(
                            record['Processed Date Time']),
                        Volume=record['Volume'],
                        VolumeUnit=record['Volume Unit'],
                        NumberOfChildren=record['No. of Children'],
                        SiteHeld=siteheld,
                        ImportId=ImportId,
                    ) for index, record in parent_df.iterrows()
                ]
                ProcessedReport.objects.bulk_create(model_instances)
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Processed file data - {e}')
                return None

            # Dropping duplicates in file comparing with
            # ProcessedAliquots table
            processed_aliquots_barcode = ProcessedAliquots.objects.\
                values_list('AliquotId', flat=True)[
                    ::1]
            child_df = child_df[~child_df['Sample ID'].isin(
                processed_aliquots_barcode)]

            # Bulk uploading to ProcessedAliquots table
            try:
                model_instances = [
                    ProcessedAliquots(
                        SampleType=dict((v, k) for k, v in sample_type.items()).
                        get(record["Sample Type"]),
                        Volume=record['Volume'],
                        VolumeUnit=record['Volume Unit'],
                        PostProcessingStatus=0,
                        ParentID=ProcessedReport.objects.filter(
                            Barcode=record['Participant ID']).first().ParentId,
                        AliquotId=record['Sample ID'],
                    ) for index, record in child_df.iterrows()
                ]
                ProcessedAliquots.objects.bulk_create(model_instances)
            except Exception as e:
                logger.error(f'Something went wrong in uploading \
                    Processed Aliquots file data - {e}')
                return None

            manifest_db_df = \
                manifest_db_df[manifest_db_df['Participant ID'].isin(
                    parent_df['Participant ID'].tolist())]

            # Updating the Bloodsamples State based on processing time to
            # PROCESSED_ON_TIME or PROCESSED_NOT_ON_TIME
            processed_not_on_time = 0
            for index, row in manifest_db_df.iterrows():

                blood_samples = BloodSample.objects.filter(
                    Barcode=row['Participant ID'])
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
            # try:
            #     for index, row in parent_df[parent_df['No. of Children'] < 6].\
            #             iterrows():
            #         blood_samples = BloodSample.objects.filter(
            #             Barcode=row['Participant ID'])
            #         for sample in blood_samples:
            #             sample.State = 2
            #             sample.save()
            # except Exception as e:
            #     logger.error(f'Something went wrong in updating \
            #         Blood Sample records to unable to process due to \
            #             less aliquots - {e}')
            #     return None

            # Mailing all blood sample Data Manager if any
            # PROCESSED_NOT_ON_TIME records are uploaded
            try:
                if processed_not_on_time > 0:
                    msg_html = render_to_string(
                        'mail-aliquots-less.html', {
                            'processed_not_on_time': processed_not_on_time,
                            'referer': request.headers['Referer'][:-1]
                        })
                    send_mail(
                        'Blood Samples - Uploaded Processed records which are \
                            not processed under 36 hours',
                        msg_html,
                        settings.DEFAULT_FROM_EMAIL,
                        [i.user_id.email for i in UserRoles.objects.filter(
                            role_id__in=[2])],  # This should be list of from users
                        html_message=msg_html,
                    )
            except Exception as e:
                logger.error('Something went wrong in sending \
                    mail to data managers about uploads of \
                        not processed under 36 hours - {e}')
                return None

            return render(request, self.receipt_success_template, {
                "total_records": total_records,
                "processed_on_time": manifest_db_df.greaterthan_36hrs[
                    manifest_db_df.greaterthan_36hrs == False].count(),
                "processed_not_on_time": manifest_db_df.greaterthan_36hrs[
                    manifest_db_df.greaterthan_36hrs == True].count(),
                "less_aliquots_cnt": parent_df['No. of Children'][
                    parent_df['No. of Children'] < 6].count(),
                "barcode_existance": receipt_barcode_existance,
            })

        return render(request, self.receipt_confirm_template, {
            "total_records": total_records,
            "processed_on_time": manifest_db_df.greaterthan_36hrs[
                manifest_db_df.greaterthan_36hrs == False].count(),
            "processed_not_on_time": manifest_db_df.greaterthan_36hrs[
                manifest_db_df.greaterthan_36hrs == True].count(),
            "less_aliquots_cnt": parent_df['No. of Children'][
                parent_df['No. of Children'] < 6].count(),
            "barcode_existance": receipt_barcode_existance,
        })
