from django.urls import path
from .views import *
from .upload_views import *
from .review_views import *
from .review_edit_views import *
from .download_views import *
from .report_views import *

app_name = 'Blood Sample'

urlpatterns = [
    path('', HomeView.as_view(), name='Home'),
    path('upload', UploadView.as_view(),
         name='Upload'),
    path('upload_blood_sample', UploadBloodSampleView.as_view(),
         name='UploadBloodSample'),
    path('upload_manifest', UploadManifestView.as_view(),
         name='UploadManifest'),
    path('upload_receipt', UploadReceiptView.as_view(),
         name='UploadManifest'),
    path('upload_processed', UploadProcessedView.as_view(),
         name='UploadProcessed'),
    path('download_blood_sample', DownloadBloodSampleView.as_view(),
         name='DownloadBloodSample'),
    path('filter_options', FilterOptionsView.as_view(),
         name='filterOptions'),
    path('settings_options', SettingsOptionsView.as_view(),
         name='SettingsOptions'),
    path('download_aliquots', DownloadAliquotsView.as_view(),
         name='DownloadAliquots'),
    path('review', ReviewView.as_view(),
         name='Review'),
    path('unmatched_manifest', UnmachedManifestView.as_view(),
         name='UnmachedManifest'),
    path('unmatched_receipt', UnmachedReceiptView.as_view(),
         name='UnmachedReceipt'),
    path('unmatched_processed', UnmachedProcessedView.as_view(),
         name='UnmachedProcessed'),
    path('edit_blood_sample', EditBloodSampleView.as_view(),
         name='EditBloodSample'),
    path('edit_manifest', EditManifestView.as_view(),
         name='EditManifest'),
    path('edit_receipt', EditReceiptView.as_view(),
         name='EditReceipt'),
    path('edit_processed_bs', EditProcessedBsView.as_view(),
         name='EditProcessedBs'),
    path('edit_processed', EditProcessedView.as_view(),
         name='EditProcessed'),
    path('get_manifest_filters', GetManifestFiltersView.as_view(),
         name='GetManifestFilters'),
     path('home_tab', HomeTabView.as_view(),
         name='HomeTab'),
     path('final_state_chart', FinalStateChartView.as_view(),
         name='FinalStateChart'),
     path('nurse_stats_chart', NurseStatsChartView.as_view(),
         name='NurseStatsChart'),
     path('unresolved_chart', UnresolvedChartView.as_view(),
         name='UnresolvedChart'),
     path('processed_not_on_time_chart', ProcessedNotOnTimeView.as_view(),
         name='ProcessedNotOnTime'),

]
