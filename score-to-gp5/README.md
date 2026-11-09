# 谱图转 GP5 · score-to-gp5 0.1.0

可独立分发的本地 Codex 插件。**宿主 Codex 负责看谱图，脚本负责整理、验证和导出**；不包含自动识谱模型，不调用收费识图 API，不要求 OpenAI API key。

流程：图片/PDF → 页面与来源清单 → Codex 视觉转录 → `guitar-notation/1.0` → 确定性校验 → `score.gp5` + `score.playback.json` + 回读报告。

## 使用

安装/启用插件后可说：

> 使用 $score-to-gp5，读取 origin_score 中的吉他谱，按记谱 schema 提取并生成 GP5。输出放到 outputs/my-song。

识谱与代码执行需要支持本地文件、图片读取和 Python 的宿主。仅复制包不会让当前聊天热加载技能；可直接让 Codex 读取 `skills/score-to-gp5/SKILL.md` 来使用本地流程。插件未发布到公共目录。

依赖统一在用户指定的环境运行。当前项目示例：

```sh
conda run -n agent python -m pip install -r /absolute/path/to/score-to-gp5/requirements.txt
```

只有用户授权安装时才执行安装命令。依赖包括 PyGuitarPro 0.11、jsonschema、PyMuPDF、Pillow；插件不内置第三方库或字体。

## CLI

以下命令从插件根目录运行，输出路径按用户项目替换：

```sh
conda run -n agent python skills/score-to-gp5/scripts/pipeline.py doctor
conda run -n agent python skills/score-to-gp5/scripts/pipeline.py prepare /path/to/scores --out /path/to/work/pages
# Codex 看图后编写 /path/to/work/notation.json；prepare 本身不识谱。
conda run -n agent python skills/score-to-gp5/scripts/pipeline.py validate /path/to/work/notation.json
conda run -n agent python skills/score-to-gp5/scripts/pipeline.py export /path/to/work/notation.json --out /path/to/work/export
```

现有转录 sidecar 可先迁移：

```sh
conda run -n agent python skills/score-to-gp5/scripts/pipeline.py import-legacy /path/to/song.transcription.json --out /path/to/work/notation.json
```

迁移后必须检查 issues，再 validate/export。缺少时值的播放 schema 无法无损恢复乐谱，不在 import-legacy 支持范围内。来源文件以绝对路径或相对 notation.json 的路径引用，并校验哈希；移动产物时同步迁移来源路径。

## 数据和边界

- 记谱 schema 保留时值、休止、三连音、逐弦延音、技法、来源和不确定事项；播放 schema 是已有 wav_model 0.1 的严格兼容输出。
- 单轨六弦、固定 BPM；支持局部拍号、明确长度的弱起。反复/跳房必须在识谱阶段按顺序展开。
- GP5 分开保存基础调弦和 capo；播放 schema 将 capo 加到调弦上一次。
- 击弦、勾弦、换把/连奏滑音写到 GP5 的源音上。播放 JSON 用目标音拨弦近似。
- GP5 动态力度量化为 15、31、47、63、79、95、111、127；原始力度保留在播放 JSON，差异写入报告。
- GP5 琶音使用 stroke=32，与播放 JSON 默认 30 ms 并非完全相同。
- 泛音、推弦、打板、多声部、多轨、变速需额外扩展，不能把这些符号默默忽略。
- 中文标题保留在 JSON/README；默认 GP5 内部文本使用 ASCII，避免旧格式乱码。`--encoding gbk` 可显式选择中文编码，仍需目标软件验证。
- 不输出 WAV，不捆绑原歌曲、采样库或已有谱图。

## 验证

```sh
conda run -n agent python -m unittest discover -s tests -v
conda run -n agent python skills/score-to-gp5/scripts/pipeline.py export examples/mini.notation.json --out /tmp/gp5-example
```

测试覆盖特殊调弦+capo、三连音、跨小节连音、H/P/滑音、变拍号、弱起、输入哈希、输出防覆盖与错误数据拒绝。真实回归使用项目已有《情歌》70 小节/666 音符、《流行的云》84 小节/822 音符，均通过本次读回验证；曲谱不随插件分发。

结构回读不证明看图无误，也不代表已在 Guitar Pro 应用内打开或试听。来源识读仍需逐乐行核对。

## 打包和安装源

当前仓库的 `tools/package_score_to_gp5.py` 会创建 ZIP 和本地 marketplace 目录。包包含 `plugin.json`（portable manifest）、`.codex-plugin/plugin.json`（兼容 manifest）、一个技能及其脚本/schema、合成测试短句和测试；无 MCP 或启动 hooks。

本地 marketplace 根目录含 `.agents/plugins/marketplace.json` 和 `plugins/score-to-gp5/`。可以按宿主支持的本地插件流程安装；CLI 注册入口为 `codex plugin marketplace add /absolute/path/to/marketplace-root`，之后在应用插件目录安装并在新聊天验证。生成包不会替用户执行全局注册或宣称已经启用。

格式依据：[OpenAI 插件打包文档](https://developers.openai.com/plugins/build/plugins)。
