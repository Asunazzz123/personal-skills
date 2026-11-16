import copy
from pathlib import Path
import sys
import tempfile
import unittest
import guitarpro

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/score-to-gp5/scripts'))
import pipeline
import performance


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'input.json'
        self.data=pipeline.read(ROOT/'examples/mini.notation.json')
        self.data['schema_version']='guitar-notation/1.1'
        self.data['metadata']['capo_fret']=2
        self.data['measures']=[{'number':1,'events':[
            {'beat':'0','duration':'1','notes':[{'string':2,'fret':0,'harmonic':{'type':'artificial','touch_fret':12}}]},
            {'beat':'1','duration':'1','notes':[{'string':2,'fret':0,'harmonic':{'type':'tapped','touch_fret':12}}]},
            {'beat':'2','duration':'1','capo_change':4,'notes':[{'string':1,'fret':12,'harmonic':{'type':'natural'}}],
             'percussion':[{'kind':'body_hit','sound':'low_wood_block'}]},
            {'beat':'3','duration':'1','notes':[{'string':6,'fret':0,'dead':True}], 'attack':'slapping'}]}]

    def test_effects_and_capo_routing(self):
        pipeline.save(self.path,self.data);r=pipeline.export(self.path,self.root/'out')
        self.assertEqual(r['counts']['harmonics'],3)
        self.assertEqual(r['counts']['dead_notes'],1)
        self.assertEqual(r['counts']['percussion_hits'],1)
        song=guitarpro.parse(str(self.root/'out/score.gp5'))
        a,b,d=song.tracks
        self.assertEqual((a.offset,b.offset,d.channel.channel),(2,4,9))
        self.assertEqual(a.measures[0].voices[0].beats[2].status.name,'rest')
        self.assertEqual(b.measures[0].voices[0].beats[0].status.name,'rest')
        self.assertFalse(a.measures[0].voices[0].beats[1].notes[0].effect.letRing)
        self.assertEqual(d.measures[0].voices[0].beats[2].notes[0].value,77)
        plan=pipeline.read(self.root/'out/score.performance.json')
        self.assertEqual(plan['events'][0]['notes'][0]['sounding_midi'],71)
        self.assertEqual(plan['events'][2]['notes'][0]['sounding_midi'],78)
        self.assertIsNone(plan['events'][3]['notes'][0]['sounding_midi'])
        self.assertFalse((self.root/'out/score.playback.json').exists())

    def test_capo_cannot_carry_tie(self):
        self.data['measures'][0]['events'][2]['notes'][0]['tie']=True
        with self.assertRaisesRegex(ValueError,'capo transition'):performance.validate(self.data,self.path)

    def test_harmonic_touch_is_explicit(self):
        self.data['measures'][0]['events'][0]['notes'][0]['harmonic']['touch_fret']=7
        with self.assertRaisesRegex(ValueError,'touch_fret'):performance.validate(self.data,self.path)

    def test_dead_harmonic_rejected(self):
        self.data['measures'][0]['events'][0]['notes'][0]['dead']=True
        with self.assertRaisesRegex(ValueError,'Dead note'):performance.validate(self.data,self.path)

    def test_harmonic_tie_cannot_change_type(self):
        self.data['measures'][0]['events'][1]['notes'][0]['tie']=True
        with self.assertRaisesRegex(ValueError,'Tie changes'):performance.validate(self.data,self.path)

    def test_percussion_only_event(self):
        e=self.data['measures'][0]['events'][0]
        e['notes']=[];e['percussion']=[{'kind':'string_slap','sound':'side_stick'}]
        pipeline.save(self.path,self.data)
        report=pipeline.export(self.path,self.root/'out')
        self.assertEqual(report['counts']['percussion_hits'],2)

    def test_duplicate_percussion_rejected(self):
        e=self.data['measures'][0]['events'][2]
        e['percussion']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate simultaneous'):performance.validate(self.data,self.path)


if __name__=='__main__':unittest.main()
