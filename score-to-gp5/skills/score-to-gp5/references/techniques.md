# guitar-notation/1.1 技法扩展

使用 `notation-v1.1.schema.json`；1.0 文件仍走原导出器。1.1 新增以下可选字段，未出现时不推断技法：

| 层级 | 字段 | 含义 |
|---|---|---|
| measure | source_measure | 反复展开前的原谱小节号 |
| event | capo_change: 4 | 从这个时点起 capo 改为 4，后续持续生效 |
| event | attack | tapping / slapping / popping，GP5 原生拍点效果 |
| event | percussion | 独立的打击动作，可与旋律同时存在 |
| event | text | 演奏说明 |
| note | dead: true | X 闷音，无确定音高，不是休止 |
| note | palm_mute / accent | 掌根闷音、重音 |
| note | harmonic | natural / artificial / tapped；见下例 |

```json
{"string":2,"fret":0,"harmonic":{"type":"artificial","touch_fret":12}}
```

人工/拍弦泛音当前支持触点距按弦位置 12 品的八度泛音。`touch_fret` 和 `fret` 均相对 capo。自然泛音支持 5、7、12 品节点；分别对应空弦上方 24、19、12 半音。其他节点拒绝导出，不悄悄套用八度。泛音到普通音的变化需要在目标音上明确取消 harmonic；tie 的类型与品位必须完全一致。

```json
{"kind":"string_slap","sound":"side_stick","velocity":79}
```

percussion.kind 区分 string_slap / body_hit；sound 显式选择 side_stick（GM 37）、low_wood_block（77）、acoustic_bass_drum（35）。这些是可审查的替代音色，不代表逼真吉他录音。同一事件可同时含 notes 和 percussion，不删掉旋律。只有打击时 notes=[]，不设 rest=true。

## 移夹与轨道

每种 capo 单独一条吉他轨，保持完整同步时间轴；其他轨在该时点休止。打击轨使用 MIDI 通道 10（代码索引 9），与吉他分离。换夹时释放旧轨最近的逐弦延续，禁止跨 capo 的 tie/H/P/slide；不会合成移夹过程的连续滑音。边界释放及目标应用中的实际声音仍需试听。

## 输出和校验

同一个 `pipeline.py validate/export` 命令自动按版本分流。1.1 输出 `score.gp5`、`score.performance.json`、`verification.json`、`README.txt`。**不会冒充输出兼容播放 schema 0.1 的无损文件**：原 WAV 合成器无法读取 performance/1.1，尚未实现这些打击采样与泛音音源。

回读覆盖所有轨、拍点时长、起音、音符类型、力度、H/P/slide、泛音类型和触点、拍弦效果、打击音符与 capo/通道。不得只对第一条轨验收。遇到源谱含糊标记，记录来源和假设；不要把节拍重排的练习版标成完整原版。

## guitar-notation/1.2 电吉他扩展

使用 `notation-v1.2.schema.json`，兼容 1.1 的字段；相同 export 命令生成 GP5 和 performance/1.2。

- metadata.midi_program：0–127，零起算 GM 音色；29 为 overdriven guitar。
- note.bend：`type` 为 bend/bendRelease/bendReleaseBend/prebend/prebendRelease；`points` 的 position 严格递增，从 0 到 12，按该音符时值归一化。semitones 为 0–12 整数；半音推弦 1，全音推弦 2。延音跨槽时需显式写出后续的预推/回落曲线，不能默认恢复原音高。
- note.grace：fret、transition（none/slide/hammer/bend）、duration（16/32/64），可选 on_beat。只支持附属于一个主音的单音装饰音；无对应主音的装饰和弦声部须保留注释并披露。
- note.vibrato、staccato、let_ring：布尔值；最后一项可覆盖全曲的延音设置。
- event.pick_stroke：up/down，原谱没有标记时不自动添加。

回读比较包含曲线控制点、装饰音属性、拨片方向、揉弦、断奏与 MIDI 音色。推弦过程的精确时间、装饰音时值和未印出的力度是演奏约定，应在 issues 中标明，不能当作实测信息。
