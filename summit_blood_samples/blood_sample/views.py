import re
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View


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
            SELECT DISTINCT DATE(bs."CreatedAt"),\
                to_char(bs."CreatedAt",'Month DD, YYYY' ) as dates
            FROM blood_sample_bloodsample as bs
            left join blood_sample_manifestrecords as mr on \
                bs."CohortId" = mr."CohortId"
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
            SELECT DISTINCT Date(mr."CollectionDateTime"), \
                to_char(mr."CollectionDateTime",'Month DD, YYYY' ) as dates
            FROM "blood_sample_manifestrecords" as mr
            left join blood_sample_bloodsample as bs on \
                bs."CohortId" = mr."CohortId"
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
            SELECT DISTINCT Date(mr."CollectionDateTime"), \
                to_char(mr."CollectionDateTime",'Month DD, YYYY' ) as dates
            FROM "blood_sample_manifestrecords" as mr
            left join blood_sample_receiptrecords as rr on \
                rr."Barcode" = mr."Barcode"
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
            SELECT DISTINCT Date(rr."DateTimeTaken"), \
                to_char(rr."DateTimeTaken",'Month DD, YYYY' ) as dates
            FROM "blood_sample_receiptrecords" as rr
            left join blood_sample_manifestrecords as mr on \
                rr."Barcode" = mr."Barcode"
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
            inner join blood_sample_manifestrecords as mr on \
                (rr."Barcode" = mr."Barcode")
            inner join blood_sample_bloodsample as bs on \
                (bs."CohortId" = mr."CohortId")
            WHERE rr."SampleId" not in (
                SELECT
                    "pr"."ParentId"
                FROM blood_sample_processedreport as pr
                join blood_sample_receiptrecords as rr on \
                    pr."ParentId" = rr."SampleId"
                join blood_sample_manifestrecords as mr on \
                    rr."Barcode" = mr."Barcode"
                join blood_sample_bloodsample as bs on \
                    bs."CohortId" = mr."CohortId"
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
                    inner join blood_sample_manifestrecords as mr on \
                        rr."Barcode" = mr."Barcode"
                    inner join blood_sample_bloodsample as bs on \
                        bs."CohortId" = mr."CohortId"
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

