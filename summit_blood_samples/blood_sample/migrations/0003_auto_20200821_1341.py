# Generated by Django 3.0.8 on 2020-08-21 13:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blood_sample', '0002_auto_20200817_1526'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='bloodsample',
            index=models.Index(fields=['CreatedAt', 'State'], name='CreatedAt_and_State_idx'),
        ),
        migrations.AddIndex(
            model_name='bloodsample',
            index=models.Index(fields=['CohortId'], name='CohortId_bs_idx'),
        ),
        migrations.AddIndex(
            model_name='bloodsampleimport',
            index=models.Index(fields=['CreatedAt'], name='CreatedAt_bs_import_idx'),
        ),
        migrations.AddIndex(
            model_name='manifestimports',
            index=models.Index(fields=['CreatedAt'], name='CreatedAt_mf_import_idx'),
        ),
        migrations.AddIndex(
            model_name='manifestrecords',
            index=models.Index(fields=['CollectionDateTime', 'Site', 'Visit', 'Room'], name='CDT_S_V_R_mr_idx'),
        ),
        migrations.AddIndex(
            model_name='manifestrecords',
            index=models.Index(fields=['CollectionDateTime', 'Visit', 'Room'], name='CDT_V_R_idx'),
        ),
        migrations.AddIndex(
            model_name='manifestrecords',
            index=models.Index(fields=['CohortId'], name='CohortId_mr_idx'),
        ),
        migrations.AddIndex(
            model_name='manifestrecords',
            index=models.Index(fields=['Barcode'], name='Barcode_mr_idx'),
        ),
        migrations.AddIndex(
            model_name='processedimports',
            index=models.Index(fields=['CreatedAt'], name='CreatedAt_pr_import_idx'),
        ),
        migrations.AddIndex(
            model_name='processedreport',
            index=models.Index(fields=['ParentId'], name='ParentId_pr_idx'),
        ),
        migrations.AddIndex(
            model_name='processedreport',
            index=models.Index(fields=['ProcessedDateTime'], name='ProcessedDateTime_pr_idx'),
        ),
        migrations.AddIndex(
            model_name='processedreport',
            index=models.Index(fields=['ReceivedDateTime'], name='ReceivedDateTime_pr_idx'),
        ),
        migrations.AddIndex(
            model_name='receiptimports',
            index=models.Index(fields=['CreatedAt'], name='CreatedAt_rr_import_idx'),
        ),
        migrations.AddIndex(
            model_name='receiptrecords',
            index=models.Index(fields=['Barcode'], name='Barcode_rr_idx'),
        ),
        migrations.AddIndex(
            model_name='receiptrecords',
            index=models.Index(fields=['DateTimeTaken'], name='DateTimeTaken_rr_idx'),
        ),
        migrations.AddIndex(
            model_name='receiptrecords',
            index=models.Index(fields=['SampleId'], name='SampleId_rr_idx'),
        ),
    ]
