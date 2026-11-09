# guitar-notation/1.0

完整字段约束见 notation.schema.json。所有 beat/duration/length_beats 用四分音符为一拍的有理数字符串：`1/2` 是八分，`1/3` 是八分三连音，`1/6` 是十六分三连音。不可写 0.333333 近似。beat 为小节内零起点，事件覆盖全小节，无隐含时间空洞；休止也占时值。

metadata 必须有 title、bpm、tempo_status（printed/user/estimated）、capo_fret、tuning_midi_6_to_1、meter（如 [4,4]）、let_ring。调弦为上 capo 之前的 MIDI，品位相对 capo。C–G–D–G–A–D = [36,43,50,55,57,62]；capo=9 的播放 schema 调弦应为 [45,52,59,64,66,71]，GP5 仍保存基础调弦 + offset 9。

每个 measures[] 项包含 number、events，可有 meter 覆盖和 length_beats（用于弱起，须不超过当前拍号长度）。导出 GP5 会将弱起/不完整小节转换成等长局部拍号并报告，不隐藏时长变化。常规小节可不写 length_beats。

notes 每项为 {string:1..6, fret:0..36, tie:false, velocity:1..127}。默认 velocity=102。tie=true 表示续接该弦最近相同品位；不能同时带技法。无 notes 的事件必须 rest=true。休止只表达不拨新音，默认 let-ring 不会自动制掉其他弦。

technique_from_previous 在目标音上写 hammer_on / pull_off / shift_slide / legato_slide；脚本会把 GP 效果放到上一同弦源音，保证音高方向正确，且两个音所在事件相邻。其他语义不能借这些字段冒充。

arpeggio=low_to_high / high_to_low 仅用于两个及以上新音，不混用 tie。GP5 以 32 分音符 stroke 记谱；播放 schema 使用 arpeggio_ms（默认30）。没有毫秒级一致性保证。

sources 是 {id,path,sha256,page?} 清单，path 相对 notation.json 或绝对路径。measure.source_id 与可选 bbox 连接到来源。校验时核对存在的文件哈希；缺失文件会阻止导出，确保未把复制/移动失败当作有来源。

issues 为 {status:unresolved/assumption,message,measure?}。unresolved 阻止导出；assumption 明确写入报告。不得通过批量改 status 来掩盖未读清内容。

JSON 模板在插件根目录 examples/mini.notation.json。GP5 内部文本默认 ASCII，中文曲名完整保留在 JSON/README；可显式传 --encoding gbk，但目标软件的文字编码兼容性需验证。
