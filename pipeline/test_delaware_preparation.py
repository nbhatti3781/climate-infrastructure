"""Offline regression tests; synthetic geometries never become dashboard data."""
import unittest
from unittest.mock import patch
from shapely.geometry import box, LineString
from process_national_assessment import (CoverageBlocked, flood_footprint,
                                        polygon_from_esri, projected_county, road_network)
from process_state_assessment import esri_polygon
from ec2.prepare_shutdown import prepare
from ec2.check_guard import check
from datetime import datetime, timezone


class PreparationTests(unittest.TestCase):
    def test_road_duplicates_union_and_clip_at_county(self):
        area=box(-76.01,39,-76,39.01)
        geographic,county,crs,project=projected_county(esri_polygon(area),'10001')
        feature={'geometry':{'paths':[[(-76.02,39.005),(-75.99,39.005)]]}}
        source=type('Source',(),{'arcgis':lambda *args,**kwargs:[feature,feature]})()
        network,count=road_network(source,county,geographic,project)
        self.assertEqual(count,4)
        self.assertLess(network.length,900)
        self.assertGreater(network.length,800)  # metres, no duplicate counting

    def test_nfhl_gap_breakdown_keeps_hole_unknown(self):
        area=box(0,0,4,4)
        polygon=area.difference(box(1,1,2,2))
        feature={'geometry':esri_polygon(polygon),'attributes':{'FLD_ZONE':'X','SFHA_TF':'F'}}
        source=type('Source',(),{'arcgis':lambda *a,**k:[feature]})()
        identity=type('Identity',(),{'transform':staticmethod(lambda x,y:(x,y))})()
        with self.assertRaises(CoverageBlocked) as error:
            flood_footprint(source,area,area,identity,LineString([(0,1.5),(4,1.5)]))
        audit=error.exception.diagnostics
        self.assertGreater(audit['outside_any_returned_zone_road_miles'],0)
        self.assertEqual(audit['explicitly_undetermined_or_unmapped_road_miles'],0)

    def test_known_zone_x_is_measured_zero_not_unmapped(self):
        area=box(0,0,4,4)
        feature={'geometry':esri_polygon(area),'attributes':{'FLD_ZONE':'X','SFHA_TF':'F'}}
        source=type('Source',(),{'arcgis':lambda *a,**k:[feature]})()
        identity=type('Identity',(),{'transform':staticmethod(lambda x,y:(x,y))})()
        footprint,audit=flood_footprint(source,area,area,identity,LineString([(0,1),(4,1)]))
        self.assertTrue(footprint.is_empty)
        self.assertEqual(audit['unknown_road_miles'],0)

    def test_external_stop_scoped_to_one_ohio_instance_and_utc_deadline(self):
        plan=prepare('i-0123456789abcdef0','123456789012','climate-stop','2026-10-18T10:00:00Z')
        schedule=plan['stop-schedule']
        self.assertEqual(schedule['ScheduleExpression'],'at(2026-10-18T12:03:00)')
        self.assertEqual(schedule['FlexibleTimeWindow'],{'Mode':'OFF'})
        self.assertEqual(plan['stop-policy']['Statement'][0]['Resource'],
                         'arn:aws:ec2:us-east-2:123456789012:instance/i-0123456789abcdef0')

    def test_expired_external_guard_prevents_job_restart(self):
        evidence={'verified':True,'region':'us-east-2','launch_time':'2026-10-18T10:00:00Z',
                  'deadline':'2026-10-18T12:03:00Z'}
        with self.assertRaises(ValueError):
            check(evidence,datetime(2026,10,18,13,tzinfo=timezone.utc),
                  datetime(2026,10,18,10,tzinfo=timezone.utc))


if __name__=='__main__':
    unittest.main()
