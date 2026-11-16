"""Notation 1.1/1.2: explicit effects, capo routing and a separate percussion track.

Does not emit lossy playback 0.1. performance.json preserves the timed actions
for a future sampler; the existing WAV renderer cannot consume it.
"""
from pathlib import Path
from fractions import Fraction
import copy
import json
import tempfile
import guitarpro
from guitarpro import models as m
import jsonschema
import pipeline as base

SOUNDS={'side_stick':37,'low_wood_block':77,'acoustic_bass_drum':35}
NATURAL={12:12,7:19,5:24}


def musical_pitch(note,meta,capo):
    if note.get('dead'):return None
    open_pitch=meta['tuning_midi_6_to_1'][6-note['string']]+capo
    harmonic=note.get('harmonic')
    if not harmonic:return open_pitch+note['fret']
    if harmonic['type']=='natural':return open_pitch+NATURAL[note['fret']]
    return open_pitch+note['fret']+12


def validate(data,path,verify_sources=True):
    jsonschema.Draft202012Validator(base.read(base.REF/('notation-v1.2.schema.json' if data['schema_version']=='guitar-notation/1.2' else 'notation-v1.1.schema.json'))).validate(data)
    plain=copy.deepcopy(data);plain['schema_version']='guitar-notation/1.0'
    plain['metadata'].pop('midi_program',None)
    capo=data['metadata']['capo_fret'];last={};event_count=0;changes=[]
    for b,pb in zip(data['measures'],plain['measures']):
        pb.pop('source_measure',None)
        for e,pe in zip(b['events'],pb['events']):
            if 'capo_change' in e:
                if any(n.get('tie') or n.get('technique_from_previous') for n in e['notes']):
                    raise ValueError('Cannot continue ties/legato across a capo transition')
                if capo!=e['capo_change']:
                    capo=e['capo_change'];last.clear();changes.append({'measure':b['number'],'beat':e['beat'],'capo':capo})
            for k in ('capo_change','text','attack','percussion','pick_stroke'):pe.pop(k,None)
            if not e['notes'] and e.get('attack'):
                raise ValueError('Guitar attack requires guitar notes; use percussion for a standalone hit')
            if e.get('rest') and (e['notes'] or e.get('percussion')):
                raise ValueError('Rest cannot contain pitched or percussion attacks')
            if not e['notes']:pe['rest']=True
            for n,pn in zip(e['notes'],pe['notes']):
                s=n['string'];prev=last.get(s);h=n.get('harmonic')
                if n.get('dead') and (n.get('tie') or h or n.get('technique_from_previous')):
                    raise ValueError('Dead note cannot be a tie, harmonic or legato destination')
                if h:
                    if h['type']=='natural':
                        if n['fret'] not in NATURAL or 'touch_fret' in h:raise ValueError('Natural harmonic supports nodes 5/7/12 only')
                    elif h.get('touch_fret')!=n['fret']+12:
                        raise ValueError('Artificial/tapped harmonic requires explicit octave touch_fret = fret + 12')
                if n.get('tie'):
                    if prev is None or prev['note'].get('dead') or prev['note']['fret']!=n['fret'] or prev['note'].get('harmonic')!=h:
                        raise ValueError('Tie changes fret, harmonic, capo or has no pitched source')
                if n.get('technique_from_previous') and (prev is None or prev['note'].get('dead') or prev['index']!=event_count-1):
                    raise ValueError('Legato cannot originate from a dead note or cross a capo boundary')
                pitch=musical_pitch(n,data['metadata'],capo)
                if pitch is not None and not 0<=pitch<=127:raise ValueError('Sounding harmonic/pitched MIDI note out of range')
                last[s]={'note':n,'index':event_count}
                bend=n.get('bend')
                if bend:
                    points=bend['points'];positions=[p['position'] for p in points]
                    if positions[0]!=0 or positions[-1]!=12 or positions!=sorted(set(positions)):
                        raise ValueError('Bend positions must strictly increase from 0 to 12')
                    if n.get('dead') or h:raise ValueError('Bend cannot combine with dead note or harmonic')
                    if pitch+max(p['semitones'] for p in points)>127:raise ValueError('Bent MIDI pitch out of range')
                if n.get('grace') and (n.get('tie') or n.get('dead') or h or n.get('technique_from_previous')):
                    raise ValueError('Grace requires a fresh, ordinary destination note')
                for k in ('dead','harmonic','palm_mute','accent','bend','vibrato','staccato','grace','let_ring'):pn.pop(k,None)
            perc=e.get('percussion',[])
            if len({p['sound'] for p in perc})!=len(perc):raise ValueError('Duplicate simultaneous percussion sound')
            event_count+=1
    result=base.validate(plain,path,verify_sources)
    # GP5 has a finite MIDI channel pool. Use one track per distinct capo value.
    caps={data['metadata']['capo_fret'],*[c['capo'] for c in changes]}
    if len(caps)>7:raise ValueError('At most seven distinct capo tracks supported')
    result.update(capo_changes=changes,distinct_capos=sorted(caps))
    return result


def velocity(v):return min(range(15,128,16),key=lambda x:abs(x-v))


def harmonic_signature(h):
    if not h:return None
    if isinstance(h,m.ArtificialHarmonic):return ('artificial',h.pitch.just,h.pitch.accidental,h.octave.value)
    if isinstance(h,m.TappedHarmonic):return ('tapped',h.fret)
    return ('natural',)


def electric_signature(e):
    bend=(e.bend.type.name,e.bend.value,tuple((p.position,p.value,p.vibrato) for p in e.bend.points)) if e.bend else None
    g=e.grace
    grace=(g.fret,g.duration,g.transition.name,g.isOnBeat,g.velocity,g.isDead) if g else None
    return (bend,grace,e.vibrato,e.staccato)


def fingerprint(song):
    return {'tempo':song.tempo,'tracks':[{
        'name':t.name,'capo':t.offset,'percussion':t.isPercussionTrack,
        'channel':t.channel.channel,'effect_channel':t.channel.effectChannel,'program':t.channel.instrument,
        'strings':[(s.number,s.value) for s in t.strings],
        'bars':[{'start':me.start,'meter':(me.header.timeSignature.numerator,me.header.timeSignature.denominator.value),
          'beats':[{'start':b.start,'ticks':b.duration.time,'status':b.status.name,'text':b.text,
           'attack':b.effect.slapEffect.name,'pick_stroke':b.effect.pickStroke.name,'stroke':(b.effect.stroke.direction.name,b.effect.stroke.value),
           'notes':[(n.string,n.value,n.type.name,n.velocity,n.effect.letRing,n.effect.palmMute,n.effect.accentuatedNote,
                     n.effect.hammer,tuple(s.name for s in n.effect.slides),harmonic_signature(n.effect.harmonic),electric_signature(n.effect)) for n in sorted(b.notes,key=lambda n:n.string)]
          } for b in me.voices[0].beats]} for me in t.measures]
        } for t in song.tracks]}


def build(data,encoding='ascii'):
    meta=data['metadata'];caps=sorted({meta['capo_fret'],*[e['capo_change'] for b in data['measures'] for e in b['events'] if 'capo_change' in e]})
    label=lambda s:(s.encode('ascii','ignore').decode().strip() or 'Guitar Score') if encoding=='ascii' else s
    song=m.Song(title=label(meta['title']),artist=label(meta.get('artist','')) if meta.get('artist') else '',tempo=meta['bpm'])
    song.instructions='Source transcription; see notation JSON and verification report for source-specific assumptions.'
    song.notice=[label(i['message']) for i in data['issues']]
    song.measureHeaders=[];song.tracks=[];tracks={};channel_pairs=[(0,1),(2,3),(4,5),(6,7),(8,10),(11,12),(13,14)]
    for i,c in enumerate(caps):
        track=m.Track(song,number=i+1,name=f'Guitar - Capo {c}',offset=c,fretCount=36,
            strings=[m.GuitarString(s+1,p) for s,p in enumerate(reversed(meta['tuning_midi_6_to_1']))],
            channel=m.MidiChannel(channel=channel_pairs[i][0],effectChannel=channel_pairs[i][1],instrument=meta.get('midi_program',25)))
        track.measures=[];song.tracks.append(track);tracks[c]=track
    drum=None
    if any(e.get('percussion') for b in data['measures'] for e in b['events']):
        drum=m.Track(song,number=len(song.tracks)+1,name='Percussion - approximate',isPercussionTrack=True,
                     channel=m.MidiChannel(channel=9,effectChannel=9,instrument=0))
        drum.measures=[];song.tracks.append(drum)
    absolute=Fraction();capo=meta['capo_fret'];last={};plan=[];expected=[];changes=[]
    for b in data['measures']:
        meter=b.get('meter',meta['meter']);length=Fraction(b.get('length_beats',str(Fraction(meter[0]*4,meter[1]))))
        if length!=Fraction(meter[0]*4,meter[1]):q=length/4;meter=[q.numerator,q.denominator]
        header=m.MeasureHeader(number=b['number'],start=960+int(absolute*960),timeSignature=m.TimeSignature(meter[0],m.Duration(meter[1])))
        song.measureHeaders.append(header)
        for t in song.tracks:t.measures.append(m.Measure(t,header))
        for ei,e in enumerate(b['events']):
            at=absolute+Fraction(e['beat']);start=960+int(at*960)
            if 'capo_change' in e and e['capo_change']!=capo:
                # Release the most recent voice on every old string at its written end.
                for n in last.values():n.effect.letRing=False
                changes.append({'at_beat':str(at),'from':capo,'to':e['capo_change'],'release_previous':True})
                capo=e['capo_change'];last={}
            beats={}
            for t in song.tracks:
                voice=t.measures[-1].voices[0]
                beat=m.Beat(voice,start=start,duration=base.duration(e['duration']),status=m.BeatStatus.rest)
                voice.beats.append(beat);beats[t.number]=beat
            track=tracks[capo];beat=beats[track.number]
            labels=[]
            if 'source_measure' in b and ei==0:labels.append(f'Source bar {b["source_measure"]}')
            if e.get('text'):labels.append(label(e['text']))
            if 'capo_change' in e:labels.append(f'Capo -> {capo}; switch guitar track')
            if labels:beat.text=' | '.join(labels)
            for n in e['notes']:
                s,f=n['string'],n['fret'];tech=n.get('technique_from_previous');harm=n.get('harmonic')
                if tech in ('hammer_on','pull_off'):last[s].effect.hammer=True
                elif tech:last[s].effect.slides=[m.SlideType.shiftSlideTo if tech=='shift_slide' else m.SlideType.legatoSlideTo]
                effect=m.NoteEffect(letRing=n.get('let_ring',meta['let_ring']) and not n.get('dead'),palmMute=n.get('palm_mute',False),accentuatedNote=n.get('accent',False))
                effect.vibrato=n.get('vibrato',False);effect.staccato=n.get('staccato',False)
                if n.get('bend'):
                    bd=n['bend'];effect.bend=m.BendEffect(type=getattr(m.BendType,bd['type']),value=100*max(p['semitones'] for p in bd['points']),points=[m.BendPoint(p['position'],p['semitones']) for p in bd['points']])
                if n.get('grace'):
                    g=n['grace'];effect.grace=m.GraceEffect(fret=g['fret'],duration=g['duration'],transition=getattr(m.GraceEffectTransition,g['transition']),isOnBeat=g.get('on_beat',False),velocity=95)
                if harm:
                    if harm['type']=='natural':effect.harmonic=m.NaturalHarmonic()
                    elif harm['type']=='tapped':effect.harmonic=m.TappedHarmonic(fret=harm['touch_fret'])
                    else:effect.harmonic=m.ArtificialHarmonic(pitch=m.PitchClass((meta['tuning_midi_6_to_1'][6-s]+f)%12),octave=m.Octave.ottava)
                typ=m.NoteType.dead if n.get('dead') else m.NoteType.tie if n.get('tie') else m.NoteType.normal
                note=m.Note(beat,string=s,value=f,type=typ,velocity=velocity(n.get('velocity',102)),effect=effect)
                beat.notes.append(note);beat.status=m.BeatStatus.normal;last[s]=note
                expected.append((track.number,int(at*960),s,f,typ.name,harmonic_signature(effect.harmonic)))
            if e.get('pick_stroke'):beat.effect.pickStroke=getattr(m.BeatStrokeDirection,e['pick_stroke'])
            if e.get('attack'):beat.effect.slapEffect=getattr(m.SlapEffect,e['attack'])
            if e.get('arpeggio'):beat.effect.stroke=m.BeatStroke(m.BeatStrokeDirection.down if e['arpeggio']=='low_to_high' else m.BeatStrokeDirection.up,32)
            for i,p in enumerate(e.get('percussion',[])):
                db=beats[drum.number];db.status=m.BeatStatus.normal
                db.notes.append(m.Note(db,string=i+1,value=SOUNDS[p['sound']],type=m.NoteType.normal,velocity=velocity(p.get('velocity',79))))
                db.text=(' / '.join(x['kind'] for x in e['percussion']))+' (GM proxy)'
            plan.append({'measure':b['number'],'source_measure':b.get('source_measure'),'at_beat':str(at),
                         'duration':e['duration'],'capo':capo,'notes':[dict(n,sounding_midi=musical_pitch(n,meta,capo)) for n in e['notes']],
                         'percussion':[dict(p,gm_note=SOUNDS[p['sound']]) for p in e.get('percussion',[])],
                         'pick_stroke':e.get('pick_stroke'),'attack':e.get('attack'),'arpeggio':e.get('arpeggio'),'arpeggio_ms':e.get('arpeggio_ms',30) if e.get('arpeggio') else None})
        absolute+=length
    return song,{'schema_version':'guitar-performance/1.2' if data['schema_version']=='guitar-notation/1.2' else 'guitar-performance/1.1','midi_program':meta.get('midi_program',25),'bpm':meta['bpm'],'capo_changes':changes,'events':plan,
                 'renderer_status':'No WAV renderer for this schema yet; not compatible with playback 0.1.'},expected


def export(input_path,out,force=False,encoding='ascii'):
    input_path=Path(input_path).resolve();data=base.read(input_path);summary=validate(data,input_path)
    out=Path(out).resolve();names=['score.gp5','score.performance.json','verification.json','README.txt']
    targets=base.destinations([out/n for n in names],[input_path,*base.source_paths(data,input_path)],force)
    song,plan,expected=build(data,encoding);out.mkdir(parents=True,exist_ok=True)
    enc='cp1252' if encoding=='ascii' else encoding
    with tempfile.TemporaryDirectory(prefix='.gp5-',dir=out) as tmp:
        stage=Path(tmp);guitarpro.write(song,str(stage/names[0]),version=(5,1,0),encoding=enc)
        parsed=guitarpro.parse(str(stage/names[0]),encoding=enc)
        if fingerprint(song)!=fingerprint(parsed):raise ValueError('Extended GP5 roundtrip changed effects/notes/tracks')
        actual=[(t.number,b.start-960,n.string,n.value,n.type.name,harmonic_signature(n.effect.harmonic)) for t in parsed.tracks if not t.isPercussionTrack for me in t.measures for b in me.voices[0].beats for n in b.notes]
        if sorted(actual,key=repr)!=sorted(expected,key=repr):raise ValueError('Extended guitar events differ from notation')
        for t in parsed.tracks:
            for me in t.measures:
                if sum(b.duration.time for b in me.voices[0].beats)!=me.header.length:raise ValueError('Track timeline mismatch')
        counts={'harmonics':0,'dead_notes':0,'hammer_sources':0,'slide_sources':0,'percussion_hits':0,'bends':0,'graces':0,'vibrato':0,'staccato':0}
        for t in parsed.tracks:
            for me in t.measures:
                for b in me.voices[0].beats:
                    for n in b.notes:
                        counts['bends']+=n.effect.bend is not None
                        counts['graces']+=n.effect.grace is not None
                        counts['vibrato']+=n.effect.vibrato
                        counts['staccato']+=n.effect.staccato
                        counts['harmonics']+=n.effect.harmonic is not None
                        counts['dead_notes']+=n.type==m.NoteType.dead
                        counts['hammer_sources']+=n.effect.hammer
                        counts['slide_sources']+=bool(n.effect.slides)
                        counts['percussion_hits']+=t.isPercussionTrack
        report={**summary,'counts':counts,'tracks':[{'name':t.name,'capo':t.offset,'percussion':t.isPercussionTrack,'channel':t.channel.channel} for t in parsed.tracks],
                'source_sha256':base.digest(input_path),'gp5_sha256':base.digest(stage/names[0]),'roundtrip':'passed: all tracks, timing, frets, dynamics, harmonics, legato, bend curves, grace notes, vibrato, staccato, pick strokes, percussion and capo routing',
                'bpm':song.tempo,'issues':data['issues'],'guitar_pro_app_verified':False,
                'limitations':(['GM drum sounds are proxies for guitar string/body percussion.'] if counts['percussion_hits'] else [])
                              +(['Capo switches use separate tracks; no continuous capo-motion sound.'] if summary['capo_changes'] else [])
                              +['GP5 velocity uses discrete dynamics; bend timing and grace durations are not measured performance timing.',
                                'performance JSON is an extended event plan, not playable by wav_model schema 0.1.']}
        base.save(stage/names[1],plan);base.save(stage/names[2],report)
        (stage/names[3]).write_text(data['metadata']['title']+'\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for name,target in zip(names,targets):(stage/name).replace(target)
    return report
