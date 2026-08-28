from django.db import connection

class SpatialAssigner:
    ### Assign administrative boundaries to earthquake events using PostGIS.

    def assign_country(self, earthquake_id):
        ### Assign the ADM0 country containing the earthquake point.
        ### ST_Covers is used so points located exactly on a boundary are included.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tbl_earthquake AS e
                SET
                    country = c.country,
                    country_code = c.country_code
                FROM tbl_boundary_country AS c
                WHERE e.id = %s
                  AND ST_Covers(c.geometry, e.geometry);
                """,
                [earthquake_id],
            )

            return cursor.rowcount

    def assign_region(self, earthquake_id):
        ### Assign the ADM1 region containing the earthquake point.
        ### The country_code filter restricts the spatial search to the assigned country.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tbl_earthquake AS e
                SET
                    region = r.region,
                    region_code = r.region_code
                FROM tbl_boundary_region AS r
                WHERE e.id = %s
                  AND e.country_code = r.country_code
                  AND ST_Covers(r.geometry, e.geometry);
                """,
                [earthquake_id],
            )

            return cursor.rowcount

    def assign_earthquake(self, earthquake_id):
        ### Clear previously derived administrative values before recalculation.
        ### This prevents stale country or region values when an event changes
        ### location or is located outside all available boundaries.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tbl_earthquake
                SET
                    country = NULL,
                    country_code = NULL,
                    region = NULL,
                    region_code = NULL
                WHERE id = %s;
                """,
                [earthquake_id],
            )

        ### Assign country first because ADM1 assignment depends on country_code.
        country_assigned = self.assign_country(earthquake_id)

        if country_assigned == 0:
            ### The earthquake may be located outside all available ADM0 boundaries.
            return False

        ### Assign the ADM1 region using the country assigned by the ADM0 lookup.
        self.assign_region(earthquake_id)

        return True

    def reassign_all(self):
        ### Recalculate spatial attributes for every earthquake from its geometry.
        ### Existing country and region values are intentionally overwritten.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tbl_earthquake AS e
                SET
                    country = c.country,
                    country_code = c.country_code
                FROM tbl_boundary_country AS c
                WHERE ST_Covers(c.geometry, e.geometry);
                """
            )

            countries_assigned = cursor.rowcount

            ### Clear previous ADM1 values before recalculating them.
            ### This prevents historical values from surviving when no ADM1 matches.
            cursor.execute(
                """
                UPDATE tbl_earthquake
                SET
                    region = NULL,
                    region_code = NULL;
                """
            )

            cursor.execute(
                """
                UPDATE tbl_earthquake AS e
                SET
                    region = r.region,
                    region_code = r.region_code
                FROM tbl_boundary_region AS r
                WHERE e.country_code = r.country_code
                  AND ST_Covers(r.geometry, e.geometry);
                """
            )

            regions_assigned = cursor.rowcount

        return countries_assigned, regions_assigned