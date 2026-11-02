import sys
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_grounding import split_vmd,patch_root_track,floor_lifts,bone_name


class GroundingContracts(unittest.TestCase):
    def fixture(self,roots=1):
        def record(name,frame):
            return name.encode('cp932').ljust(15,b'\0')+struct.pack('<Ifff4f',frame,1,2,3,0,0,0,1)+bytes(range(64))
        records=[record('全ての親',0) for i in range(roots)]+[record('左足首',7),record('右足',12)]
        header=b'Vocaloid Motion Data 0002'.ljust(30,b'\0')+b'fixture'.ljust(20,b'\0')
        return header+struct.pack('<I',len(records))+b''.join(records)+b'opaque trailing sections: preserve all bytes'

    def test_surgical_patch_preserves_other_tracks_header_and_tail(self):
        original=self.fixture(); result=patch_root_track(original,[0,.005,.002],(0,12.5,0))
        h,a,t=split_vmd(original);hh,b,tt=split_vmd(result)
        self.assertEqual((h,t),(hh,tt));self.assertTrue(all(len(r)==111 for r in b))
        self.assertEqual([r for r in a if bone_name(r)!='全ての親'],[r for r in b if bone_name(r)!='全ての親'])
        root=[r for r in b if bone_name(r)=='全ての親']
        self.assertEqual(len(root),3)
        self.assertEqual([struct.unpack_from('<I',r,15)[0] for r in root],[0,1,2])
        self.assertAlmostEqual(struct.unpack_from('<fff',root[1],19)[1],2+.0625)
        self.assertTrue(all(r[31:47]==a[0][31:47] for r in root))

    def test_rejects_ambiguous_roots_and_truncated_bone_sections(self):
        for count in (0,2):
            with self.assertRaises(ValueError):patch_root_track(self.fixture(count),[0],(0,1,0))
        with self.assertRaises(ValueError):split_vmd(self.fixture()[:80])

    def test_smoothing_never_reintroduces_floor_penetration(self):
        heights=[.002]*5+[-.005]+[.002]*5
        lift=floor_lifts(heights)
        self.assertTrue(all(h+d>=.0005-1e-10 for h,d in zip(heights,lift)))
        self.assertGreater(lift[4],0);self.assertGreater(lift[6],0)
        with self.assertRaises(ValueError):floor_lifts([-.10])
        with self.assertRaises(ValueError):floor_lifts([float('nan')])

if __name__=='__main__':unittest.main()
