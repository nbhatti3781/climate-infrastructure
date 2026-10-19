"""Shared state adapters must preserve county source-selection semantics."""
import tempfile
import unittest
from shapely.geometry import Polygon

from process_state_assessment import IndexedLayer, StateSources, esri_polygon
from process_national_assessment import HPMS_2024, TIGER_PRIMARY_ROADS, FEMA_NFHL, Blocked, polygon_from_esri


class StateTests(unittest.TestCase):
    def test_index_preserves_boundary_crossings(self):
        features=[{'attributes':{'OBJECTID':i},'geometry':{'paths':[line]}}
                  for i,line in enumerate([[(0,0),(4,0)],[(8,8),(9,9)],[(2,0),(2,4)]])]
        layer=IndexedLayer(features)
        selected=layer.query({'geometry':'1,-1,3,1','geometryType':'esriGeometryEnvelope'})
        self.assertEqual({f['attributes']['OBJECTID'] for f in selected},{0,2})

    def test_polygon_holes_survive_shared_projection(self):
        polygon=Polygon([(0,0),(4,0),(4,4),(0,4)],holes=[[(1,1),(1,2),(2,2),(2,1)]])
        self.assertTrue(polygon.equals(polygon_from_esri(esri_polygon(polygon))))

    def test_traffic_state_partition_matches_county_pagination(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=[{':id':str(i),'county_id':c,'aadt':10,'line':None} for i,c in enumerate([1,1,3])]
            source=StateSources(directory,32,[],{},rows,None,{},'unavailable')
            where='stateid=10 AND county_id=1 AND f_system <= 4'
            self.assertEqual(source.get(HPMS_2024,{'$select':'count(*) AS n','$where':where}),[{'n':'2'}])
            page=source.get(HPMS_2024,{'$select':':id,aadt,line','$where':where,'$offset':1,'$limit':1})
            self.assertEqual(page[0][':id'],'1')

    def test_shared_flood_failure_does_not_invent_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            source=StateSources(directory,32,[],{},[],None,{},'HTTP 500')
            with self.assertRaisesRegex(Blocked,'unavailable'):
                source.arcgis(FEMA_NFHL+'/28/query',{})


if __name__=='__main__':
    unittest.main()
