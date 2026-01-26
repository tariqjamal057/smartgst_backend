from django.core.management.base import BaseCommand

from tenants.models import Company, Domain


class Command(BaseCommand):
    help = "Creates the public tenant"

    def handle(self, *args, **options):
        # Create public tenant
        if not Company.objects.filter(schema_name="public").exists():
            public_tenant = Company(
                schema_name="public", name="Public Tenant", subdomain_name="public"
            )
            public_tenant.save()
            self.stdout.write(self.style.SUCCESS("Public tenant created."))

            # Add domain
            domain = Domain()
            domain.domain = "localhost"  # NOTE: like this for local development
            domain.tenant = public_tenant
            domain.is_primary = True
            domain.save()
            self.stdout.write(self.style.SUCCESS('Domain "localhost" created for public tenant.'))
        else:
            self.stdout.write(self.style.WARNING("Public tenant already exists."))
