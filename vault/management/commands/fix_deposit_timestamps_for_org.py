from django.core.management.base import BaseCommand
from django.db.models import Max

from vault.models import Organization, Collection, Deposit, DepositFile


class Command(BaseCommand):
    help = "Fix missing Deposit timestamps for given org with DepositFile timestamps"

    def add_arguments(self, parser):
        parser.add_argument("organization_id", type=int, help="The Organization ID")

    def handle(self, *args, **options):
        org = Organization.objects.get(id=options["organization_id"])
        fix_deposit_timestamps_for_org(org)


def fix_deposit_timestamps_for_org(org: Organization):
    deposits = Deposit.objects.filter(
        organization=org,
        state__in=[Deposit.State.HASHED, Deposit.State.REPLICATED],
    )
    for deposit in deposits:
        last_upload_at = DepositFile.objects.filter(deposit=deposit).aggregate(
            last_upload_at=Max("uploaded_at")
        )["last_upload_at"]
        last_hashed_at = DepositFile.objects.filter(deposit=deposit).aggregate(
            last_hashed_at=Max("hashed_at")
        )["last_hashed_at"]
        if deposit.uploaded_at is None:
            deposit.uploaded_at = last_upload_at
        if deposit.hashed_at is None:
            deposit.hashed_at = last_hashed_at
        deposit.save()
