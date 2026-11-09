import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import guitarpro
from PIL import Image
import fitz

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pipeline',ROOT/'skills/score-to-gp5/scripts/pipeline.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=p.read(ROOT/'examples/mini.notation.json')
        self.input=self.root/'notation.json';p.save(self.input,self.data)

    def test_roundtrip_and_capo(self):
        r=p.export(self.input,self.root/'out')
        self.assertEqual(r['roundtrip'],'passed')
        s=guitarpro.parse(str(self.root/'out/score.gp5'));t=s.tracks[0]
        self.assertEqual(t.offset,9)
        self.assertEqual([x.value for x in t.strings],[62,57,55,50,43,36])
        self.assertEqual(t.measures[1].header.timeSignature.numerator,3)
        b=t.measures[0].voices[0].beats
        self.assertEqual(b[1].duration.time,320)
        self.assertTrue(b[1].notes[0].effect.hammer)
        self.assertTrue(b[2].notes[0].effect.hammer)
        self.assertEqual(b[4].notes[0].type.name,'tie')
        self.assertEqual(b[1].notes[0].velocity,95)
        playback=p.read(self.root/'out/score.playback.json')
        self.assertEqual(playback['instrument']['tuning_midi_6_to_1'],[45,52,59,64,66,71])
        self.assertEqual(len(playback['events']),7)
        self.assertEqual(len(b),6)

    def test_bad_rhythm(self):
        self.data['measures'][0]['events'][1]['beat']='2'
        with self.assertRaisesRegex(ValueError,'gap/overlap'):p.validate(self.data,self.input)

    def test_unresolved(self):
        self.data['issues'].append({'status':'unresolved','message':'Unreadable fret'})
        with self.assertRaisesRegex(ValueError,'Unresolved'):p.validate(self.data,self.input)

    def test_orphan_tie(self):
        self.data['measures'][0]['events'][1]['notes'][0]['tie']=True
        with self.assertRaisesRegex(ValueError,'orphan'):p.validate(self.data,self.input)

    def test_duplicate_string(self):
        self.data['measures'][0]['events'][-1]['notes']=[{'string':2,'fret':0},{'string':2,'fret':2}]
        with self.assertRaisesRegex(ValueError,'duplicate string'):p.validate(self.data,self.input)

    def test_unknown_effect_not_silently_dropped(self):
        self.data['measures'][0]['events'][1]['notes'][0]['harmonic']=True
        with self.assertRaises(Exception):p.validate(self.data,self.input)

    def test_changed_source(self):
        s=self.root/'source.png';s.write_bytes(b'old')
        self.data['sources']=[{'id':'s','path':'source.png','sha256':p.digest(s)}]
        s.write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'changed'):p.validate(self.data,self.input)

    def test_nonrepresentable_duration(self):
        with self.assertRaises(ValueError):p.duration('1/7')

    def test_wrong_hammer_direction(self):
        self.data['measures'][0]['events'][2]['notes'][0]['fret']=0
        with self.assertRaisesRegex(ValueError,'direction'):p.validate(self.data,self.input)

    def test_output_collision(self):
        with self.assertRaisesRegex(ValueError,'collide'):p.destinations([self.input],[self.input],True)

    def test_no_implicit_overwrite(self):
        p.export(self.input,self.root/'out')
        with self.assertRaisesRegex(ValueError,'exists'):p.export(self.input,self.root/'out')

    def test_partial_measure(self):
        self.data['measures']=[{'number':1,'length_beats':'1','events':[{'beat':'0','duration':'1','notes':[{'string':1,'fret':0}]}]}]
        p.save(self.input,self.data);r=p.export(self.input,self.root/'out')
        s=guitarpro.parse(str(self.root/'out/score.gp5'))
        self.assertEqual(s.measureHeaders[0].timeSignature.numerator,1)
        self.assertEqual(r['quarter_beats'],'1')

    def test_prepare_images_natural_order_and_pdf(self):
        source=self.root/'images';source.mkdir()
        Image.new('RGB',(120,80),'white').save(source/'page10.png')
        Image.new('RGB',(120,80),'white').save(source/'page2.png')
        r=p.prepare(source,self.root/'pages');manifest=p.read(r['manifest'])
        self.assertTrue(manifest['pages'][0]['path'].endswith('page2.png'))
        doc=fitz.open();doc.new_page();doc.new_page();doc.save(self.root/'input.pdf');doc.close()
        self.assertEqual(p.prepare(self.root/'input.pdf',self.root/'pdf-pages')['pages'],2)

    def test_legacy_unknown_information_blocked(self):
        old={'title':'test','bpm':80,'meter':'4/4','capo_fret':0,'tuning_midi_6_to_1':[40,45,50,55,59,64],
             'bars':[{'number':1,'events':[{'beat':'0','duration':'4','notes':[[1,0]],'harmonic':True}]}]}
        path=self.root/'legacy.json';p.save(path,old)
        p.import_legacy(path,self.input,True)
        with self.assertRaisesRegex(ValueError,'Unresolved'):p.validate(p.read(self.input),self.input)


if __name__=='__main__':unittest.main()
