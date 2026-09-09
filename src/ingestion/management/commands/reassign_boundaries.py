from django.core.management.base import BaseCommand

from ingestion.spatial_assigner import SpatialAssigner


class Command(BaseCommand):
    help = "Reassign earthquake country and region attributes using PostGIS boundaries."

    def handle(self, *args, **options):
        ### Recalculate country and region assignments for every earthquake.
        ### SpatialAssigner owns the PostGIS logic so the same operation can
        ### also be reused by other ingestion workflows in the future.
        assigner = SpatialAssigner()

        countries_assigned, regions_assigned = assigner.reassign_all()

        ### Report the number of earthquake records matched by each boundary level.
        self.stdout.write(
            self.style.SUCCESS(
                f"Countries assigned: {countries_assigned}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Regions assigned: {regions_assigned}"
            )
        )