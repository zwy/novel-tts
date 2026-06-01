# novel-tts Qwen3-TTS 改进计划

## 背景
当前项目已集成 Qwen3-TTS 的 `generate_custom_voice` 基础功能，但仅使用了 `text`/`language`/`speaker` 三个参数，未利用 Qwen3-TTS 的核心控制特性（`instruct` 情感/风格指令、`flash_attention_2` 加速、模型能力查询等）。

## 改进目标
补全 Qwen3-TTS CustomVoice 的核心使用能力，提升推理性能和 API 易用性，保持向后兼容。

---

## 改动清单

### 1. `novel_tts/config.py` — 配置扩展
- **添加 `use_flash_attention2: bool = False`**：控制是否启用 `flash_attention_2`（GPU 显存有限时可选开启）。
- **`ModelInfo` 添加可选 `model_type: str = "customvoice"`**：为后续扩展 VoiceClone / VoiceDesign 预留字段，当前不启用行为变更。

### 2. `novel_tts/tts_engine.py` — 核心引擎增强
- **`synthesize` 添加 `instruct: str | None = None` 参数**：
  - 若有值，传给 `generate_custom_voice(..., instruct=instruct)`。
  - 若无值，不传（保持现有行为）。
- **添加 `_build_instruct(speed, pitch, volume) -> str | None` 辅助方法**：
  - 将数值参数自动转换为中文自然语言 instruct，例如 `speed=1.2` → `"语速稍快一些"`，`volume=0.8` → `"音量稍小一些"`。
  - 多个参数组合时用逗号连接。
  - 全为默认值（`None` 或 1.0）时返回 `None`。
- **添加 `get_supported_speakers() -> list[str]` / `get_supported_languages() -> list[str]`**：
  - 调用 `self._model.get_supported_speakers()` / `get_supported_languages()`，若模型未加载则先 `load()`。
- **模型加载支持 `flash_attention_2`**：
  - `load()` 中根据配置决定是否传入 `attn_implementation="flash_attention_2"`。
  - 若配置开启但环境未安装 `flash_attn`，捕获 `ImportError` 降级为 `"eager"` 并记录 warning。

### 3. `novel_tts/schemas.py` — 请求 Schema 完善
- **添加 `instruct: str | None = None`**：用户可直接传入自然语言风格/情感指令（如 `"用温柔悲伤的语气朗读"`），优先级高于自动生成的参数 instruct。
- **`speed`/`pitch`/`volume` 添加 `Field(ge=0.1, le=3.0)` 范围校验**：当前仅定义类型，无范围约束。

### 4. `novel_tts/api.py` — API 规范化与新接口
- **`create_job` 改用 `CreateJobRequest` schema**：
  - 当前为 `body: dict`，直接替换为 `body: CreateJobRequest`。
  - `params_json` 仍序列化完整 body，保持与现有数据库兼容。
- **添加查询接口**：
  - `GET /v1/models/{model_id}/speakers` → 返回该模型支持的 speaker 列表。
  - `GET /v1/models/{model_id}/languages` → 返回该模型支持的语言列表。
  - 若模型未加载，在接口内触发惰性加载。

### 5. `novel_tts/worker.py` — Worker 传递 instruct
- **`process_job` 解析 `params_json`**：
  - 提取 `instruct`、`speed`、`pitch`、`volume`。
  - **优先级**：若用户显式传了 `instruct`，直接使用；否则调用 `_build_instruct` 从数值参数生成；若都没有则为 `None`。
  - 将 `instruct` 传入 `tts_engine.synthesize(..., instruct=...)`。

### 6. 测试更新
- **`test_tts_engine.py`**：
  - 补充 `synthesize` 传递 `instruct` 的测试。
  - 补充 `_build_instruct` 生成逻辑的测试（单参数、多参数组合、全默认值返回 None）。
  - 补充 `flash_attention_2` 开启时的加载逻辑测试（mock `shutil.which("sox")` + mock `Qwen3TTSModel.from_pretrained` 验证参数）。
- **`test_jobs_api.py`**：
  - 将现有 `body: dict` payload 改为符合 `CreateJobRequest` 的字段（移除不存在的 `narrator_default` profile，改用项目已定义的 `female_calm` 等，或保持 `"narrator_default"` 因为映射有 fallback）。
  - 添加 `/v1/models/{model_id}/speakers` 和 `/languages` 接口测试（使用 FakeTTSEngine  mock `get_supported_speakers`）。

---

## 向后兼容性
- `instruct` 为可选参数，不传时行为与现有代码完全一致。
- `speed`/`pitch`/`volume` 原为可选且未生效，现仅在用户传入且未传 `instruct` 时自动生效，属于新增功能而非破坏变更。
- `create_job` 从 `dict` 改为 `CreateJobRequest`：字段名完全一致，FastAPI 会自动解析相同 JSON，API 契约不变。

---

## 不涉及的范围（建议后续迭代）
- **VoiceClone / VoiceDesign 模式**：当前模型注册仅包含 CustomVoice。添加克隆/设计模式需要引入参考音频上传、存储、复用缓存等新模块，建议作为独立 feature 后续实现。
- **流式生成**：worker 当前为批量分段合成后合并 WAV，流式模式适合实时场景，与当前"整章异步任务"的架构差异较大。
