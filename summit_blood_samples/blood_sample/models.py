from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User


class BloodSampleImport(models.Model):
    FilePath = models.CharField(max_length=500)
    OriginalFileName = models.CharField(max_length=500)
    CreatedBy = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='BloodSampleCreatedBy')
    CreatedAt = models.DateTimeField()
    Deleted = models.BooleanField()
    Reviewed = models.BooleanField()

    def __str__(self):
        return str(self.pk)

    class Meta:
        indexes = [
            models.Index(fields=['CreatedAt'], name='CreatedAt_bs_import_idx'),
        ]


STATECHOICE = [
    (0, 'ACTIVE'),
    (1, 'UNABLE_TO_DRAW'),
    (2, 'UNABLE_TO_PROCESS'),
    (3, 'PROCESSED_ON_TIME'),
    (4, 'PROCESSED_NOT_ON_TIME'),
]


class BloodSample(models.Model):
    id = models.BigIntegerField(primary_key=True)
    CohortId = models.CharField(max_length=7,)
    Barcode = models.CharField(max_length=10)
    AppointmentId = models.BigIntegerField()
    SiteNurseEmail = models.CharField(max_length=255)
    ImportId = models.ForeignKey(
        BloodSampleImport, on_delete=models.CASCADE,
        related_name='BloodSampleImportImportId')
    Comments = models.CharField(max_length=5000)
    CreatedAt = models.DateTimeField()
    State = models.CharField(
        max_length=1,
        choices=STATECHOICE,
        default=0
    )

    def __str__(self):
        return str(self.pk)

    def state_verbose(self):
        return '' if self.State == '' else dict(STATECHOICE)[int(self.State)]

    class Meta:
        indexes = [
            models.Index(fields=['CreatedAt', 'State'],
                         name="CreatedAt_and_State_idx"),
            models.Index(fields=['CohortId'], name='CohortId_bs_idx'),
        ]

    def save(self,):
        self.CohortId = self.CohortId.upper()
        self.Barcode = self.Barcode.upper()
        super(BloodSample, self).save()


class BloodSampleChanges(models.Model):
    Field = models.CharField(max_length=50)
    FromValue = models.CharField(max_length=5000)
    ChangedBy = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='BloodSampleChangedBy')
    ChangedAt = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return str(self.pk)


class ManifestImports(models.Model):
    FilePath = models.CharField(max_length=500)
    OriginalFileName = models.CharField(max_length=500)
    CreatedBy = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='ManifestRecordCreatedBy')
    CreatedAt = models.DateTimeField()
    Deleted = models.BooleanField()

    def __str__(self):
        return str(self.pk)

    class Meta:
        indexes = [
            models.Index(fields=['CreatedAt'],
                         name='CreatedAt_mf_import_idx'),
        ]


SITECHOICE = [
    (0, 'FMH'),
    (1, 'KGH'),
    (2, 'Mile End Hospital'),
    (3, 'UCLH'),
]

VISITCHOICE = [
    (0, 'Y0'),
    (1, 'Y0+3M'),
    (2, 'Y1'),
    (3, 'Y2'),
]


class ManifestRecords(models.Model):
    Visit = models.CharField(
        max_length=1,
        choices=VISITCHOICE,
    )
    ImportId = models.ForeignKey(
        ManifestImports, on_delete=models.CASCADE,
        related_name='ManifestRecordsImportId')
    Site = models.CharField(
        max_length=1,
        choices=SITECHOICE,
    )
    Room = models.CharField(max_length=20)
    CohortId = models.CharField(max_length=7)
    Barcode = models.CharField(max_length=10)
    CollectionDateTime = models.DateTimeField()
    Comments = models.CharField(max_length=5000, blank=True)

    def __str__(self):
        return str(self.pk)

    def site_verbose(self):
        return '' if self.Site == '' else dict(SITECHOICE)[int(self.Site)]

    def visit_verbose(self):
        return '' if self.Visit == '' else dict(VISITCHOICE)[int(self.Visit)]

    def save(self,):
        self.CohortId = self.CohortId.upper()
        self.Barcode = self.Barcode.upper()
        super(ManifestRecords, self).save()

    class Meta:
        indexes = [
            models.Index(
                fields=['CollectionDateTime', 'Site', 'Visit', 'Room'],
                         name="CDT_S_V_R_mr_idx"),
            models.Index(fields=['CollectionDateTime', 'Visit', 'Room'],
                         name="CDT_V_R_idx"),
            models.Index(fields=['CohortId'], name='CohortId_mr_idx'),
            models.Index(fields=['Barcode'], name='Barcode_mr_idx'),
        ]


class ManifestChanges(models.Model):
    Field = models.CharField(max_length=50)
    FromValue = models.CharField(max_length=5000)
    ChangedBy = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='ManifestChangedBy')
    ChangedAt = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return str(self.pk)


class ReceiptImports(models.Model):
    FilePath = models.CharField(max_length=500)
    OriginalFileName = models.CharField(max_length=500)
    CreatedBy = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='RecieptRecordsCreatedBy')
    CreatedAt = models.DateTimeField()
    Deleted = models.BooleanField()

    def __str__(self):
        return str(self.pk)

    class Meta:
        indexes = [
            models.Index(fields=['CreatedAt'],
                         name='CreatedAt_rr_import_idx'),
        ]


class ReceiptRecords(models.Model):
    Barcode = models.CharField(max_length=10)
    Clinic = models.CharField(max_length=50)
    DateTimeTaken = models.DateTimeField()
    SampleId = models.CharField(max_length=8)
    TissueSubType = models.CharField(max_length=4)
    ReceivedDateTime = models.DateTimeField()
    Volume = models.CharField(max_length=500)
    VolumeUnit = models.CharField(max_length=4)
    Condition = models.CharField(max_length=500)
    Comments = models.CharField(max_length=5000, blank=True)
    ImportId = models.ForeignKey(
        ReceiptImports, on_delete=models.CASCADE,
        related_name='RecieptRecordsImportId')

    def __str__(self):
        return str(self.pk)

    class Meta:
        indexes = [
            models.Index(fields=['Barcode'], name='Barcode_rr_idx'),
            models.Index(fields=['DateTimeTaken'],
                         name='DateTimeTaken_rr_idx'),
            models.Index(fields=['SampleId'], name='SampleId_rr_idx'),
        ]

    def save(self,):
        self.SampleId = self.SampleId.upper()
        self.Barcode = self.Barcode.upper()
        super(ReceiptRecords, self).save()


class ReceiptChanges(models.Model):
    Field = models.CharField(max_length=50)
    FromValue = models.CharField(max_length=5000)
    ChangedBy = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='ReceiptChangedBy')
    ChangedAt = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return str(self.pk)


class ProcessedImports(models.Model):
    FilePath = models.CharField(max_length=500)
    OriginalFileName = models.CharField(max_length=500)
    CreatedBy = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='ProcessedImportsCreatedBy')
    CreatedAt = models.DateTimeField()
    Deleted = models.BooleanField()

    def __str__(self):
        return str(self.pk)

    class Meta:
        indexes = [
            models.Index(fields=['CreatedAt'],
                         name='CreatedAt_pr_import_idx'),
        ]


SITE_HELD = [
    (0, 'UK Biocentre'),
]


class ProcessedReport(models.Model):
    Barcode = models.CharField(max_length=10)
    ParentId = models.CharField(max_length=8)
    TissueSubType = models.CharField(max_length=4)
    ReceivedDateTime = models.DateTimeField(null=True)
    ProcessedDateTime = models.DateTimeField(null=True)
    Volume = models.CharField(max_length=500)
    VolumeUnit = models.CharField(max_length=2)
    NumberOfChildren = models.CharField(max_length=500)
    Comments = models.CharField(max_length=5000, blank=True)
    SiteHeld = models.CharField(
        max_length=1,
        choices=SITE_HELD,
        default=0
    )
    ImportId = models.ForeignKey(
        ProcessedImports, on_delete=models.CASCADE,
        related_name='ProcessedImportsImportId')

    def __str__(self):
        return str(self.pk)

    class Meta:
        indexes = [
            models.Index(fields=['ParentId'], name='ParentId_pr_idx'),
            models.Index(fields=['ProcessedDateTime'],
                         name='ProcessedDateTime_pr_idx'),
            models.Index(fields=['ReceivedDateTime'],
                         name='ReceivedDateTime_pr_idx'),
        ]

    def save(self,):
        self.ParentId = self.ParentId.upper()
        super(ProcessedReport, self).save()


class ProcessedReportChanges(models.Model):
    Field = models.CharField(max_length=50)
    FromValue = models.CharField(max_length=5000)
    ChangedBy = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='ProcessedReportChangedBy')
    ChangedAt = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return str(self.pk)


PROCESSING_STATUS = [
    (0, 'Complete'),
    (1, 'Partial'),
    (2, 'Empty'),
    (3, 'Destroyed'),
    (4, 'Not applicable'),
]

SAMPLE_TYPE = [
    (0, 'RBC'),
    (1, 'Plasma'),
    (2, 'BuffyCoat'),
]


class ProcessedAliquots(models.Model):
    SampleType = models.CharField(
        max_length=1,
        choices=SAMPLE_TYPE,
    )
    Volume = models.CharField(max_length=500)
    VolumeUnit = models.CharField(max_length=2)
    PostProcessingStatus = models.CharField(
        max_length=1,
        choices=PROCESSING_STATUS,
        default=0
    )
    ParentID = models.CharField(max_length=8)
    AliquotId = models.CharField(max_length=500)

    def __str__(self):
        return str(self.pk)


class ProcessedAliquotsChanges(models.Model):
    Field = models.CharField(max_length=50)
    FromValue = models.CharField(max_length=5000)
    ChangedBy = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='ProcessedAliquotsChangedBy')
    ChangedAt = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return str(self.pk)
