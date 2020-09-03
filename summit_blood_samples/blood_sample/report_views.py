

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import JsonResponse
from django.views import View


class FinalStateChartView(LoginRequiredMixin, View):
    """
    Class for getting Final State Chart
    """

    def get(self, request, *args, **kwargs):
        """
        Method to get all the final state by days
        :param request: request object
        :return: JsonResponse object
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
        :return: JsonResponse object
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
        :return: JsonResponse object
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
                ) AS "MEH",
                SUM (CASE
                        WHEN mr."Site"='3' THEN 1
                    ELSE 0
                    END
                ) AS "UCLH"
            FROM blood_sample_manifestrecords as mr
            LEFT JOIN blood_sample_bloodsample bs on \
                "bs"."CohortId" = mr."CohortId"
            WHERE bs.id is null
            GROUP BY DATE(mr."CollectionDateTime") \
                order by DATE(mr."CollectionDateTime")
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
            "name": 'MEH',
            "data": [i['MEH'] for i in site_data]
        }, {
            "name": 'UCLH',
            "data": [i['UCLH'] for i in site_data]
        }]

        return JsonResponse({
            'status': 200,
            'site_dates': site_dates,
            'site_data': site_data,
        })


class ProcessedNotOnTimeView(LoginRequiredMixin, View):
    """
    Class for getting records that are not processed on time with day wise
    """

    def get(self, request, *args, **kwargs):
        """
        Method to get the records that are not processed on time with day wise
        :param request: request object
        :return: JsonResponse object
        """
        query = '''
            SELECT
                DATE(bs."CreatedAt"),
                count(1)
            FROM
                blood_sample_bloodsample as bs
            WHERE now() - '36 hour'::interval > bs."CreatedAt" AND \
                bs."State" in ('0','4')
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
