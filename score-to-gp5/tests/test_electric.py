"""Effects that must survive a GP5 binary roundtrip (not just JSON validation)."""
from pathlib import Path
import sys,tempfile,unittest,copy
import guitarpro
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/score-to-gp5/scripts'))
import pipeline,performance
class ElectricTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.path=self.root/'input.json'
  self.data=pipeline.read(ROOT/'examples/mini.notation.json')
  self.data['schema_version']='guitar-notation/1.2';self.data['metadata']['midi_program']=29
  self.data['measures']=[{'number':1,'events':[
   {'beat':'0','duration':'1','pick_stroke':'down','notes':[{'string':1,'fret':12,'bend':{'type':'bend','points':[{'position':0,'semitones':0},{'position':12,'semitones':2}]}}]},
   {'beat':'1','duration':'1','notes':[{'string':1,'fret':12,'tie':True,'bend':{'type':'prebendRelease','points':[{'position':0,'semitones':2},{'position':12,'semitones':0}]},'vibrato':True}]},
   {'beat':'2','duration':'1','pick_stroke':'up','notes':[{'string':2,'fret':14,'grace':{'fret':12,'transition':'hammer','duration':32},'staccato':True}]},
   {'beat':'3','duration':'1','rest':True,'notes':[]}]}]
 def test_roundtrip_effects(self):
  pipeline.save(self.path,self.data);report=pipeline.export(self.path,self.root/'out')
  t=guitarpro.parse(str(self.root/'out/score.gp5')).tracks[0];bs=t.measures[0].voices[0].beats
  self.assertEqual(t.channel.instrument,29)
  self.assertEqual([(p.position,p.value) for p in bs[0].notes[0].effect.bend.points],[(0,0),(12,2)])
  self.assertEqual(bs[1].notes[0].type.name,'tie');self.assertTrue(bs[1].notes[0].effect.vibrato)
  self.assertEqual(bs[2].notes[0].effect.grace.fret,12);self.assertTrue(bs[2].notes[0].effect.staccato)
  self.assertEqual([bs[0].effect.pickStroke.name,bs[2].effect.pickStroke.name],['down','up'])
  self.assertEqual(report['counts']['bends'],2)
 def test_bad_curve_order(self):
  self.data['measures'][0]['events'][0]['notes'][0]['bend']['points'].insert(1,{'position':12,'semitones':1})
  with self.assertRaisesRegex(ValueError,'strictly increase'):pipeline.validate(self.data,self.path)
 def test_grace_tie_rejected(self):
  self.data['measures'][0]['events'][1]['notes'][0]['grace']={'fret':10,'duration':32,'transition':'slide'}
  with self.assertRaisesRegex(ValueError,'Grace requires'):pipeline.validate(self.data,self.path)
 def test_bend_changes_detected(self):
  song,_,_=performance.build(self.data);expected=performance.fingerprint(song)
  song.tracks[0].measures[0].voices[0].beats[0].notes[0].effect.bend.points[-1].value=1
  self.assertNotEqual(expected,performance.fingerprint(song))
if __name__=='__main__':unittest.main()
