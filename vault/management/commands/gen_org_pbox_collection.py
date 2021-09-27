import os
import sys
from requests import Response
import time
from django.core.management.base import BaseCommand
from django.conf import settings

from vault.models import Organization
from internetarchive import Item, get_session

class Command(BaseCommand):
    help = "Create a petabox collection for a vault Organization and sets the Organization.pbox_collection in the database"

    def add_arguments(self, parser):
        parser.add_argument("collection_id", type=int, help="The Organization ID")
        parser.add_argument("pbox_collection_name", type=str, help="The desired Petabox collection name")
        parser.add_argument("-f", "--force", action='store_true', default=False, help="WARNING: Overwrites the existing petabox collection set for the specified Organization (Don't do this)")

    def handle(self, *args, **options):
        print(options["collection_id"], options["pbox_collection_name"], options["force"])

        try:
            organization = Organization.objects.get(id=options["collection_id"])
        except Organization.DoesNotExist:
            organization = None
            print("Organization not found")

        if organization:
            logo_path = "vault/static/vault-logo-3.png"
            metadata = {'collection': 'web-group-internal', 'mediatype': 'collection', 'creator': 'Vault', 'noindex': 'true', 'hidden': 'true', 'access-restricted': 'true', 'public-format': 'Metadata'}
            ia_session = get_session(config_file=settings.IA_CONFIG_PATH)
            item = ia_session.get_item(options["pbox_collection_name"])

            if item.exists:
                print(f"Item already exists {options['pbox_collection_name']}. Skipping")
                sys.exit(-1)

            if not os.path.isfile(logo_path):
                print(f"Logo file not found {logo_path}. Skipping")
                sys.exit(-1)

            if organization.pbox_collection is not None:
                print(f"Organization:{organization.id} already has a petabox collection set {organization.pbox_collection}.")
                if options["force"]:
                    print("!!!WARNING!!! force overwrite has been set. Organization's existing petabox collection will be overwritten")
                    print(f"\tOrganization.pbox_collection is currently {organization.pbox_collection}")
                    print(f"\tOrganization.pbox_collection will become {options['pbox_collection_name']}")
                    print("Giving you a moment to think about what you're doing...")
                    for i in range(10, 0, -1):
                        print(f"{i}", end="... ", flush=True)
                        time.sleep(1)
                else:
                    print("Skipping...")
                    sys.exit(-1)

            print(f"going to upload  into {options['pbox_collection_name']}")
            responses = item.upload(files='vault/static/vault-logo-3.png', metadata=metadata)
            if len(responses) == 1:
                print(f"S3 upload response: {responses[0].status_code}")
                if responses[0].status_code == 200:
                    print(f"Adding pbox collection to organization id:{organization.id} - {organization.name}")
                    organization.pbox_collection=options["pbox_collection_name"]
                    try:
                        organization.save()
                    except Exception as e:
                        print(f"Error saving pbox_collection to organization {organization.id} - {e}")
                        sys.exit(-1)
            else:
                print("No response from ia upload")
                sys.exit(-1)
