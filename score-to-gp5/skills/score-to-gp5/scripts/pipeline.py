"""Portable guitar TAB workflow. Image recognition is performed by the host agent."""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile

REF = Path(__file__).resolve().parents[1] / 'references'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError(f'Duplicate JSON key: {k}')
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(f'Invalid number: {s}')))


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def destinations(paths, protected=(), force=False):
    resolved = [Path(p).resolve() for p in paths]
    protected = {Path(p).resolve() for p in protected}
    if len(set(resolved)) != len(resolved) or protected.intersection(resolved):
        raise ValueError('Output paths collide with each other or an input')
    for p in resolved:
        if p.exists() and (not force or not p.is_file()):
            raise ValueError(f'Output exists (use --force for intentional replacement): {p}')
    return resolved


def source_paths(data, input_path):
    return [(Path(input_path).resolve().parent / s['path']).resolve() for s in data['sources']]


def duration(value):
    from guitarpro import models as m
    ticks = Fraction(value) * 960
    if ticks <= 0 or ticks.denominator != 1:
        raise ValueError(f'Duration is not representable at 960 ticks/quarter: {value}')
    result = m.Duration.fromTime(int(ticks))
    if result.time != ticks:
        raise ValueError(f'Duration rounded: {value}')
    return result


def validate(data, input_path, verify_sources=True):
    import jsonschema
    jsonschema.Draft202012Validator(read(REF / 'notation.schema.json')).validate(data)
    unresolved = [i for i in data['issues'] if i['status'] == 'unresolved']
    if unresolved:
        raise ValueError('Unresolved transcription issues: ' + json.dumps(unresolved, ensure_ascii=False))
    ids = [s['id'] for s in data['sources']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source IDs')
    if verify_sources:
        for source, path in zip(data['sources'], source_paths(data, input_path)):
            if not path.is_file() or digest(path) != source['sha256']:
                raise ValueError(f'Source missing or changed: {path}')
    meta = data['metadata']
    last = {}; prior_event = {}; event_index = 0; total = Fraction(); attacks = 0
    for number, bar in enumerate(data['measures'], 1):
        if bar['number'] != number:
            raise ValueError('Measures must be numbered consecutively starting at 1')
        if bar.get('source_id') and bar['source_id'] not in ids:
            raise ValueError(f'Measure {number}: unknown source_id')
        if 'bbox' in bar and not (bar['bbox'][0] < bar['bbox'][2] and bar['bbox'][1] < bar['bbox'][3]):
            raise ValueError(f'Measure {number}: invalid bbox')
        meter = bar.get('meter', meta['meter'])
        full_length = Fraction(meter[0]*4, meter[1])
        length = Fraction(bar.get('length_beats', str(full_length)))
        if not 0 < length <= full_length:
            raise ValueError(f'Measure {number}: invalid partial-measure length')
        if length != full_length and ((length/4).denominator not in (1,2,4,8,16,32,64) or (length/4).numerator > 32):
            raise ValueError('Partial measure cannot be represented by GP5 time signature')
        cursor = Fraction()
        for event in bar['events']:
            if Fraction(event['beat']) != cursor:
                raise ValueError(f'Measure {number}: gap/overlap at {event["beat"]}, expected {cursor}')
            duration(event['duration'])
            notes = event['notes']
            if bool(notes) == event.get('rest', False):
                raise ValueError(f'Measure {number}: empty notes require rest=true; rests cannot have notes')
            if len({n['string'] for n in notes}) != len(notes):
                raise ValueError(f'Measure {number}: simultaneous duplicate string')
            if 'arpeggio_ms' in event and 'arpeggio' not in event:
                raise ValueError('arpeggio_ms requires arpeggio')
            if 'arpeggio' in event and (len(notes)<2 or any(n.get('tie') for n in notes)):
                raise ValueError('Arpeggio requires at least two new notes and no ties')
            if event.get('arpeggio_ms',30)*meta['bpm']/60000 >= Fraction(event['duration']) and 'arpeggio' in event:
                raise ValueError('Arpeggio spread must be shorter than its notated slot')
            for note in notes:
                s, f = note['string'], note['fret']
                pitch = meta['tuning_midi_6_to_1'][6-s] + meta['capo_fret'] + f
                if not 0 <= pitch <= 127:
                    raise ValueError('Sounding MIDI pitch out of range')
                if note.get('tie'):
                    if last.get(s) != f or note.get('technique_from_previous'):
                        raise ValueError(f'Measure {number}: orphan/mismatched tie on string {s}')
                else:
                    attacks += 1
                technique = note.get('technique_from_previous')
                if technique:
                    if s not in last or prior_event[s] != event_index-1:
                        raise ValueError(f'Measure {number}: technique needs adjacent same-string source')
                    if (technique == 'hammer_on' and f <= last[s]) or (technique == 'pull_off' and f >= last[s]):
                        raise ValueError('Hammer/pull pitch direction mismatch')
                    if technique.endswith('slide') and f == last[s]:
                        raise ValueError('Slide destination equals source')
                last[s] = f; prior_event[s] = event_index
            event_index += 1
            cursor += Fraction(event['duration'])
        if cursor != length:
            raise ValueError(f'Measure {number}: total {cursor}, expected {length}')
        total += length
    if total*60/meta['bpm'] > 3600:
        raise ValueError('Score exceeds playback schema maximum length of 3600 seconds')
    return {'measures': len(data['measures']), 'quarter_beats': str(total), 'events': event_index,
            'new_notes': attacks, 'sources_verified': verify_sources}


def fingerprint(song):
    track = song.tracks[0]
    return {'tempo': song.tempo, 'capo': track.offset,
            'tuning': [(s.number,s.value) for s in track.strings], 'program':track.channel.instrument,
            'bars': [{'meter': (me.header.timeSignature.numerator,me.header.timeSignature.denominator.value),
                      'start': me.start, 'beats': [
                {'start':b.start,'duration':(b.duration.value,b.duration.isDotted,b.duration.tuplet.enters,b.duration.tuplet.times),
                 'ticks':b.duration.time,'status':b.status.name,
                 'stroke':(b.effect.stroke.direction.name,b.effect.stroke.value),
                 'notes':sorted((n.string,n.value,n.velocity,n.type.name,n.effect.letRing,n.effect.hammer,
                                 tuple(s.name for s in n.effect.slides)) for n in b.notes)}
                for b in me.voices[0].beats]} for me in track.measures]}


def build(data, encoding='ascii'):
    from guitarpro import models as m
    meta=data['metadata']; warnings=[]
    def label(s):
        if encoding=='ascii':
            return s.encode('ascii','ignore').decode().strip() or 'Guitar Score'
        s.encode(encoding)  # Refuse lossy metadata encoding.
        return s
    song=m.Song(title=label(meta['title']), artist=label(meta.get('artist','')) if meta.get('artist') else '',tempo=meta['bpm'])
    song.notice=['Tempo status: '+meta['tempo_status'], 'Source title and provenance are retained in notation JSON.']
    song.measureHeaders=[]
    track=m.Track(song,name='Guitar',offset=meta['capo_fret'],fretCount=36,
                  strings=[m.GuitarString(i+1,p) for i,p in enumerate(reversed(meta['tuning_midi_6_to_1']))])
    track.channel.instrument=25;track.measures=[];song.tracks=[track]
    playback={'schema_version':'0.1', 'instrument':{'sample_bank':'iowa_guitar','max_fret':36,
              'tuning_midi_6_to_1':[p+meta['capo_fret'] for p in meta['tuning_midi_6_to_1']]},
              'timebase':{'bpm':meta['bpm'],'beat_unit':'quarter_note'},
              'render':{'sample_rate':24000,'max_duration_seconds':3600},'events':[],'voicings':{}}
    absolute=Fraction(); last={}; expected=[]
    for bar in data['measures']:
        meter=bar.get('meter',meta['meter'])
        length=Fraction(bar.get('length_beats',str(Fraction(meter[0]*4,meter[1]))))
        if length!=Fraction(meter[0]*4,meter[1]):
            ratio=length/4;meter=[ratio.numerator,ratio.denominator]
            warnings.append(f'Measure {bar["number"]}: partial measure encoded as local meter {meter[0]}/{meter[1]}')
        header=m.MeasureHeader(number=bar['number'],start=960+int(absolute*960),timeSignature=m.TimeSignature(meter[0],m.Duration(meter[1])))
        song.measureHeaders.append(header);me=m.Measure(track,header);track.measures.append(me)
        voice=me.voices[0]
        for ei,event in enumerate(bar['events']):
            at=absolute+Fraction(event['beat'])
            beat=m.Beat(voice,start=960+int(at*960),duration=duration(event['duration']),
                        status=m.BeatStatus.rest if event.get('rest') else m.BeatStatus.normal)
            voice.beats.append(beat)
            for note in event['notes']:
                s,f=note['string'],note['fret'];technique=note.get('technique_from_previous')
                if technique in ('hammer_on','pull_off'):last[s].effect.hammer=True
                elif technique:last[s].effect.slides=[m.SlideType.shiftSlideTo if technique=='shift_slide' else m.SlideType.legatoSlideTo]
                raw_velocity=note.get('velocity',102)
                gp_velocity=min(range(15,128,16),key=lambda v:abs(v-raw_velocity))
                if raw_velocity!=gp_velocity:
                    warning=f'GP5 velocity quantized: {raw_velocity} -> {gp_velocity}; playback JSON preserves original velocity'
                    if warning not in warnings:warnings.append(warning)
                n=m.Note(beat,string=s,value=f,velocity=gp_velocity,
                         type=m.NoteType.tie if note.get('tie') else m.NoteType.normal,effect=m.NoteEffect(letRing=meta['let_ring']))
                beat.notes.append(n);last[s]=n
                if not note.get('tie'):
                    expected.append((int(at*960),s,f))
                    if not event.get('arpeggio'):
                        playback['events'].append({'type':'pluck','at_beat':float(at),'string':s,'fret':f,'velocity':note.get('velocity',102)/127})
            if event.get('arpeggio'):
                direction='down' if event['arpeggio']=='low_to_high' else 'up'
                beat.effect.stroke=m.BeatStroke(getattr(m.BeatStrokeDirection,direction),32)
                # Primitive plucks preserve individual velocities; high-level strum cannot.
                ordered=sorted(event['notes'],key=lambda n:n['string'],reverse=direction=='down')
                for j,n in enumerate(ordered):
                    offset=Fraction(str(event.get('arpeggio_ms',30)))*meta['bpm']/60000*j/(len(ordered)-1)
                    playback['events'].append({'type':'pluck','at_beat':float(at+offset),'string':n['string'],'fret':n['fret'],'velocity':n.get('velocity',102)/127})
                warnings.append(f'Measure {bar["number"]} event {ei}: GP stroke=32; playback spread={event.get("arpeggio_ms",30)} ms')
        absolute+=length
    if not playback['events']:
        raise ValueError('A rest-only score cannot produce playback schema 0.1')
    import jsonschema
    jsonschema.Draft202012Validator(read(REF/'playback.schema.json')).validate(playback)
    return song,playback,expected,warnings


def export(input_path, out, force=False, encoding='ascii'):
    import guitarpro
    input_path=Path(input_path).resolve();data=read(input_path)
    summary=validate(data,input_path)
    out=Path(out).resolve()
    names=['score.gp5','score.playback.json','verification.json','README.txt']
    paths=destinations([out/n for n in names],[input_path,*source_paths(data,input_path)],force)
    song,playback,expected,warnings=build(data,encoding)
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.gp5-',dir=out) as temp:
        staged=Path(temp)
        guitarpro.write(song,str(staged/names[0]),version=(5,1,0),encoding='cp1252' if encoding=='ascii' else encoding)
        parsed=guitarpro.parse(str(staged/names[0]),encoding='cp1252' if encoding=='ascii' else encoding)
        if fingerprint(parsed)!=fingerprint(song):raise ValueError('GP5 roundtrip changed musical data')
        actual=[(b.start-960,n.string,n.value) for me in parsed.tracks[0].measures for b in me.voices[0].beats for n in b.notes if n.type.name=='normal']
        if sorted(actual)!=sorted(expected):raise ValueError('GP5 attacks differ from notation')
        for measure in parsed.tracks[0].measures:
            if sum(b.duration.time for b in measure.voices[0].beats)!=measure.header.length:
                raise ValueError('GP5 measure length mismatch')
        save(staged/names[1],playback)
        report={**summary,'title':data['metadata']['title'],'bpm':song.tempo,'capo':parsed.tracks[0].offset,
                'tuning_midi_6_to_1':list(reversed([s.value for s in parsed.tracks[0].strings])),
                'source':str(input_path),'source_sha256':digest(input_path),'gp5_sha256':digest(staged/names[0]),
                'gp5_version':parsed.versionTuple,'roundtrip':'passed','issues':data['issues'],
                'warnings':warnings,'encoding':encoding,'guitar_pro_app_verified':False,
                'limitations':['Host visual transcription must be checked against source images; structural checks do not verify OCR.',
                               'Playback schema approximates techniques as plucks and does not encode notated duration or complete rest tails.',
                               'GP5 does not embed the Iowa sample bank; no audio synthesized.',
                               'ASCII mode retains the original title in JSON and README, but may simplify internal GP title.']}
        save(staged/names[2],report)
        (staged/names[3]).write_text(data['metadata']['title']+'\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for name,target in zip(names,paths):(staged/name).replace(target)
    return report


def prepare(input_path,out):
    import fitz
    from PIL import Image,ImageOps
    input_path=Path(input_path).resolve();out=Path(out).resolve()
    supported={'.png','.jpg','.jpeg','.webp','.tif','.tiff','.pdf'}
    files=[input_path] if input_path.is_file() else sorted((p for p in input_path.iterdir() if p.suffix.lower() in supported),key=lambda p:[int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',p.name)])
    if not files or any(p.suffix.lower() not in supported for p in files):raise ValueError('No supported source images/PDFs')
    if out==input_path or out in input_path.parents:raise ValueError('Output directory cannot contain/replace source root')
    if out.exists() and any(out.iterdir()):raise ValueError('prepare requires an empty output directory')
    out.mkdir(parents=True,exist_ok=True);records=[]
    for fi,path in enumerate(files,1):
        sha=digest(path)
        if path.suffix.lower()=='.pdf':
            with fitz.open(path) as doc:
                if doc.needs_pass:raise ValueError(f'Encrypted PDF: {path}')
                for pi,page in enumerate(doc,1):
                    name=f'{fi:03d}_{pi:03d}.png';page.get_pixmap(matrix=fitz.Matrix(2,2)).save(str(out/name))
                    (out/f'{fi:03d}_{pi:03d}.txt').write_text(page.get_text(),encoding='utf-8')
                    records.append({'id':f's{fi}p{pi}','path':str(path),'sha256':sha,'page':pi,'preview':name})
        else:
            with Image.open(path) as im:
                if getattr(im,'n_frames',1)!=1:raise ValueError('Multi-frame image: split frames explicitly before prepare')
                im=ImageOps.exif_transpose(im).convert('RGB');name=f'{fi:03d}_001.png';im.save(out/name)
                records.append({'id':f's{fi}p1','path':str(path),'sha256':sha,'page':1,'preview':name})
    save(out/'manifest.json',{'pages':records,'note':'Preview files are inputs to host visual reading; no musical OCR performed.'})
    return {'manifest':str(out/'manifest.json'),'pages':len(records)}


def import_legacy(input_path,out,force=False):
    input_path=Path(input_path).resolve();old=read(input_path);out=Path(out).resolve()
    destinations([out],[input_path],force)
    if 'bars' not in old:raise ValueError('Playback-only JSON lacks durations; supply a transcription sidecar')
    capo=old.get('capo_fret')
    tuning=old.get('tuning_midi_6_to_1')
    issues=[]
    if tuning is None:
        if old.get('title')=='情歌' and old.get('capo_evidence'):
            tuning=[40,45,50,55,59,64]
            issues.append({'status':'assumption','message':'Legacy Qingge uses standard tuning plus explicit capo; verify against source.'})
        else:raise ValueError('Legacy input must explicitly provide tuning_midi_6_to_1')
    if capo is None:raise ValueError('Legacy input must explicitly provide capo_fret')
    tempo=old.get('tempo',{});bpm=old.get('bpm',tempo.get('playback_bpm'))
    if not isinstance(bpm,(int,float)) or int(bpm)!=bpm:raise ValueError('Explicit integer tempo required')
    meter=old.get('meter')
    if isinstance(meter,str):meter=[int(x) for x in meter.split('/')]
    if isinstance(meter,dict):meter=[meter['numerator'],meter['denominator']]
    source={'id':'legacy','path':str(input_path),'sha256':digest(input_path)}
    result={'schema_version':'guitar-notation/1.0','metadata':{
        'title':old['title'],'bpm':int(bpm),'tempo_status':'estimated' if tempo.get('status')=='estimated_from_duration' else 'user',
        'capo_fret':capo,'tuning_midi_6_to_1':tuning,'meter':meter,'let_ring':old.get('let_ring_throughout',True)},
        'sources':[source],'measures':[],'issues':issues}
    previous=[]
    allowed={'beat','duration','notes','tied_notes','tie_from_previous','technique','technique_from','from_note','triplet','arpeggiate','rest'}
    for bar in old['bars']:
        events=[]
        for e in bar['events']:
            unknown=set(e)-allowed
            if unknown:issues.append({'status':'unresolved','measure':bar['number'],'message':'Legacy fields require review: '+','.join(sorted(unknown))})
            notes=[]
            if e.get('tie_from_previous'):
                notes=[{'string':s,'fret':f,'tie':True} for s,f in (e['notes'] or previous)]
            else:
                notes=[{'string':s,'fret':f} for s,f in e['notes']]
            notes += [{'string':s,'fret':f,'tie':True} for s,f in e.get('tied_notes',[])]
            event={'beat':e['beat'],'duration':e['duration'],'notes':notes}
            if not notes:
                event['rest']=True
                if not e.get('rest'):
                    issues.append({'status':'unresolved','measure':bar['number'],
                                   'message':'Empty legacy event has no explicit rest or usable tie source; rest is a draft placeholder only.'})
            if e.get('technique'):
                new=[n for n in notes if not n.get('tie')]
                mapping={'hammer_on':'hammer_on','pull_off':'pull_off','slide':'shift_slide'}
                if len(new)!=1 or e['technique'] not in mapping:
                    issues.append({'status':'unresolved','measure':bar['number'],'message':'Ambiguous legacy technique'})
                else:new[0]['technique_from_previous']=mapping[e['technique']]
            if e.get('arpeggiate'):
                if e['arpeggiate'] not in ('low_to_high','high_to_low'):raise ValueError('Unknown arpeggio direction')
                event['arpeggio']=e['arpeggiate']
            events.append(event)
            if e['notes']:previous=e['notes']
        result['measures'].append({'number':bar['number'],'source_id':'legacy','events':events})
    for issue in old.get('uncertainties',[]):
        issues.append({'status':'unresolved','message':'Review legacy uncertainty: '+json.dumps(issue,ensure_ascii=False)})
    for limitation in old.get('limitations',[]):
        issues.append({'status':'assumption','message':'Legacy limitation: '+limitation})
    out.parent.mkdir(parents=True,exist_ok=True);save(out,result)
    return {'notation':str(out),'issues':issues,'note':'Run validate after reviewing imported assumptions/issues.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    for name in ('prepare','validate','export','import-legacy'):
        p=sub.add_parser(name);p.add_argument('input',type=Path)
        if name!='validate':p.add_argument('--out',type=Path,required=True)
        if name in ('export','import-legacy'):p.add_argument('--force',action='store_true')
        if name=='export':p.add_argument('--encoding',default='ascii',choices=['ascii','gbk'])
    args=parser.parse_args()
    if args.command=='doctor':result={n:bool(importlib.util.find_spec(n)) for n in ('guitarpro','jsonschema','fitz','PIL')}
    elif args.command=='prepare':result=prepare(args.input,args.out)
    elif args.command=='validate':result=validate(read(args.input),args.input)
    elif args.command=='export':result=export(args.input,args.out,args.force,args.encoding)
    else:result=import_legacy(args.input,args.out,args.force)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
