# Local AV Live Translator

本地成人影片实时字幕翻译工具。

`Local AV Live Translator` 面向 Windows 本地播放场景：捕获电脑正在播放的系统声音，使用日语语音识别模型生成实时日文字幕，再通过本地 Ollama 翻译模型转换为中文字幕，并显示在置顶悬浮窗中。

> 本项目只处理本机音频，不上传视频、音频或字幕内容到云端。请仅在遵守所在地法律法规、平台规则及版权要求的前提下使用，并尊重影片相关人员的权利。

## 功能特点

- **系统声音回环采集**：捕获浏览器、播放器等程序正在播放的声音。
- **日语实时识别**：使用针对日语优化的 `kotoba-whisper-v2`。
- **本地翻译**：通过 Ollama 使用 `hy-mt2-1.8b`，音频和文本不离开本机。
- **稳定字幕流程**：ASR partial 只更新日文临时字幕，ASR final 才触发中文翻译，避免逐字翻译造成闪烁和延迟。
- **短句批量翻译**：相邻短句会合并请求，减少高频短句场景下的排队。
- **悬浮字幕窗口**：置顶、半透明、可拖动、可调整大小。

## 工作流程

```text
系统播放声音
    ↓
Windows WASAPI Loopback
    ↓
kotoba-whisper-v2（日语语音 → 日文）
    ↓
句子确认 / 短句聚合
    ↓
hy-mt2-1.8b via Ollama（日文 → 简体中文）
    ↓
PyQt6 悬浮字幕
```

## 已验证模型与配置

### 语音识别模型

- 模型：`kotoba-whisper-v2`
- 格式：CTranslate2 / faster-whisper
- 本地目录：`models/kotoba-whisper-v2.2-faster/`
- 语言：`ja`
- `beam_size=3`
- `vad_filter=True`
- `min_silence_duration_ms=300`
- `condition_on_previous_text=False`

模型目录至少应包含：

```text
models/kotoba-whisper-v2.2-faster/
├── config.json
├── model.bin
├── preprocessor_config.json
├── tokenizer.json
└── vocabulary.json
```

请将模型文件放在上述目录。模型文件较大，默认被 `.gitignore` 排除，不应提交到 GitHub。

### 模型简介与下载地址

本项目使用以下两个模型：

#### 1. kotoba-whisper-v2.2-faster（当前发布基线）

- **用途**：使用 Kotoba-Whisper v2.2 进行日语语音识别。
- **格式**：第三方转换的 CTranslate2 / faster-whisper 格式，FP32 权重。
- **来源**：[`RoachLin/kotoba-whisper-v2.2-faster`](https://huggingface.co/RoachLin/kotoba-whisper-v2.2-faster)。
- **国内镜像**：[`hf-mirror.com/RoachLin/kotoba-whisper-v2.2-faster`](https://hf-mirror.com/RoachLin/kotoba-whisper-v2.2-faster)。
- **说明**：该转换版不是 Kotoba 官方发布；本项目发布版采用它作为当前实时 ASR 基线，使用前请核对模型文件校验值。

下载后放入：

```text
models/kotoba-whisper-v2.2-faster/
```

#### 2. kotoba-whisper-v2（备用兼容版）

- **用途**：针对日语语音优化，适合本项目的日语实时字幕场景。
- **格式**：必须使用 CTranslate2 / faster-whisper 格式。
- **官方仓库**：[`kotoba-tech/kotoba-whisper-v2.0-faster`](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0-faster)
- **国内镜像仓库**：[`hf-mirror.com/kotoba-tech/kotoba-whisper-v2.0-faster`](https://hf-mirror.com/kotoba-tech/kotoba-whisper-v2.0-faster)
- **国内直链**：将仓库文件地址中的域名替换为 `hf-mirror.com`，例如：
  [`config.json`](https://hf-mirror.com/kotoba-tech/kotoba-whisper-v2.0-faster/resolve/main/config.json)、
  [`model.bin`](https://hf-mirror.com/kotoba-tech/kotoba-whisper-v2.0-faster/resolve/main/model.bin)、
  [`tokenizer.json`](https://hf-mirror.com/kotoba-tech/kotoba-whisper-v2.0-faster/resolve/main/tokenizer.json)、
  [`vocabulary.json`](https://hf-mirror.com/kotoba-tech/kotoba-whisper-v2.0-faster/resolve/main/vocabulary.json)、
  [`preprocessor_config.json`](https://hf-mirror.com/kotoba-tech/kotoba-whisper-v2.0-faster/resolve/main/preprocessor_config.json)。
- **官方直链**：对应文件可从[官方文件列表](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0-faster/tree/main)下载。

下载后放入：

```text
models/kotoba-whisper-v2/
```

如果国内镜像无法访问，再使用 Hugging Face 官方文件列表。不要下载 `.pt`、Transformers 或 Safetensors 格式文件；本项目需要 CTranslate2 / faster-whisper 格式。

### 翻译模型：hy-mt2-1.8b

- **用途**：将识别出的日文翻译为简体中文。
- **运行方式**：通过本机 Ollama API 调用，不由 Whisper 加载。
- **模型来源与命令**：
  ```bash
  ollama pull hy-mt2-1.8b
  ollama run hy-mt2-1.8b
  ```
- **国内镜像**：Ollama 模型目前没有确认到可直接替代的官方国内仓库；建议使用 Ollama 官方模型源，或按网络环境配置 Ollama 镜像。
- **API 地址**：`http://127.0.0.1:11434/api/generate`
- **推理方式**：本地 HTTP、非流式响应。
- **默认温度**：`0.1`。
- **上下文长度**：`2048`。

## 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- NVIDIA GPU（推荐；CPU 也可运行但延迟通常更高）
- Ollama
- 可用的 Windows 音频输出设备

## 显卡配置要求

本项目同时运行 Whisper 语音识别和 Ollama 翻译模型，显卡显存会直接影响实时性。以下是按当前模型组合给出的经验配置：

| 配置 | 显存 | 建议 | 说明 |
|---|---:|---|---|
| 最低可运行 | 4 GB | 不推荐 | 可能需要降低并发或改用 CPU，实时性取决于场景 |
| 入门实时 | 6 GB | 可用 | 适合 `hy-mt2-1.8b`，建议关闭其他占用显存的程序 |
| 推荐 | 8 GB | 推荐 | 适合当前 `kotoba-whisper-v2 + hy-mt2-1.8b` 组合 |
| 舒适运行 | 12 GB 及以上 | 更佳 | 余量更充足，适合高分辨率播放或同时运行其他 GPU 程序 |

### 推荐显卡档位

- **NVIDIA RTX 3060 12GB**：性价比较高，适合本项目；
- **RTX 3070 / 3080 8GB**：可以运行，注意关闭占用显存的其他程序；
- **RTX 4060 Ti 8GB / 16GB**：功耗较低，适合长时间运行；
- **RTX 4070 / 4070 Super 12GB**：推荐，实时余量较好；
- **RTX 4080 / 4090 16GB 及以上**：适合同时运行更多本地模型，但不是本项目的必需配置。

### CUDA 与驱动

- 需要安装与当前 NVIDIA 驱动兼容的 CUDA 运行库；
- `faster-whisper` 依赖 CTranslate2，GPU 运行还需要兼容的 cuBLAS 和 cuDNN；
- 新版 CTranslate2 通常面向 CUDA 12/cuDNN 9，项目虚拟环境应安装匹配的 CUDA 运行库；当前环境使用 `nvidia-cublas-cu12`；
- 显卡驱动应保持较新版本，并确认 `nvidia-smi` 能正常识别显卡。

检查显卡：

```bash
nvidia-smi
```

### 没有 NVIDIA 显卡怎么办？

可以使用 CPU 回退模式，但通常会出现：

- 首次识别延迟更高；
- 连续短句更容易形成识别积压；
- 长时间实时播放体验不如 NVIDIA GPU。

如果显存不足，优先关闭浏览器标签、游戏、视频增强软件和其他本地大模型；不要仅根据显存容量判断性能，显卡计算能力和 Ollama 实际量化版本也会影响延迟。

## 安装配置

### 1. 克隆项目

```bash
git clone <你的 GitHub 仓库地址>
cd Local_AV_Live_Translator
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv
.venv\\Scripts\\activate
```

### 3. 安装 Python 依赖

```bash
python -m pip install -r requirements.txt
```

音频采集使用 `PyAudioWPatch`。如果依赖安装后提示缺少 `pyaudiowpatch`，可单独执行：

```bash
python -m pip install PyAudioWPatch
```

### 4. 配置 NVIDIA CUDA（推荐）

使用 NVIDIA GPU 时，需要安装与当前 `faster-whisper/CTranslate2` 版本兼容的 CUDA cuBLAS 和 cuDNN。请以 `faster-whisper` 官方说明和本机驱动版本为准。

如果 CUDA 环境未配置成功，程序会尝试回退到 CPU INT8，但实时延迟可能明显增加。

### 5. 安装并准备 Ollama

安装 Ollama 后，在终端执行：

```bash
ollama pull hy-mt2-1.8b
```

`pull` 只负责下载模型，不会启动 Ollama 服务。请先启动服务：

```bash
ollama serve
```

如果使用 Ollama Desktop，也可以直接打开 Ollama 应用，由它在后台提供服务。

建议首次使用前手动预热翻译模型：

```bash
ollama run hy-mt2-1.8b
```

看到交互提示后输入一条简单测试内容，确认模型已经加载；测试完成后按 `Ctrl+D`（Windows 终端也可尝试 `Ctrl+C`）退出交互界面。这样正式启动本程序后，第一句翻译通常不会再承担模型首次加载的等待时间。

确认模型可用：

```bash
ollama list
```

运行程序前，请确保 Ollama 服务正在运行。默认地址是：

```text
http://127.0.0.1:11434
```

### 6. 准备 Whisper 模型

将 CTranslate2 格式的 `kotoba-whisper-v2` 放到：

```text
models/kotoba-whisper-v2/
```

程序当前从本地目录加载该模型，不建议在运行时临时下载模型。

## 运行

在项目根目录执行：

```bash
python main.py
```

也可以使用：

```text
run.bat
```

首次运行时，请确认 Windows 播放设备和音量正常，然后播放目标影片。程序会捕获系统输出声音并显示字幕。

## 跨电脑配置与隐私说明

项目不会依赖开发者电脑的用户名、绝对路径或固定音频设备编号。模型、翻译服务和设备都可以按当前电脑配置调整。

可选环境变量：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `LAVT_WHISPER_MODEL` | `kotoba-whisper-v2.2-faster` | Whisper 模型目录名或模型 ID |
| `LAVT_TRANSLATOR_MODEL` | `hy-mt2-1.8b` | Ollama 翻译模型名 |
| `LAVT_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama 服务地址 |
| `LAVT_AUDIO_DEVICE_INDEX` | 自动检测 | 仅在自动 Loopback 检测失败时指定设备编号 |

Windows 示例：

```bat
set LAVT_WHISPER_MODEL=kotoba-whisper-v2.2-faster
set LAVT_TRANSLATOR_MODEL=hy-mt2-1.8b
set LAVT_OLLAMA_URL=http://127.0.0.1:11434
set LAVT_AUDIO_DEVICE_INDEX=12
python main.py
```

不要把包含个人用户名、局域网地址、API 密钥、日志、影片音频或模型文件的配置和文件提交到 GitHub。项目默认通过 `.gitignore` 排除模型、日志和常见测试媒体文件。

## 音频设备说明

程序使用 Windows WASAPI Loopback 捕获系统播放声音，默认会自动匹配 Windows 当前默认输出设备对应的 Loopback 设备。设备编号由 Windows 和驱动动态分配，不同电脑通常不同。

如果没有捕获到声音：

1. 检查目标播放器是否正在播放声音；
2. 检查 Windows 默认输出设备；
3. 重新启动程序，让它重新自动检测；
4. 必要时运行设备列表功能，找到 Loopback 设备编号后设置 `LAVT_AUDIO_DEVICE_INDEX`。

设备编号只对当前电脑有效，不要把自己的设备编号写进公开源码。

## 字幕处理策略

为了避免一句话说到一半就被反复翻译，程序将 ASR 结果分为两类：

- **Partial**：只更新日文临时字幕，不请求中文翻译；
- **Final**：确认句子结束后才请求翻译；相邻短句会合并处理。

这会在极短句密集的场景中降低翻译请求排队，但最终延迟仍取决于 GPU、Ollama 模型、影片音频质量和说话速度。

## 项目结构

```text
Local_AV_Live_Translator/
├── main.py                  # 程序入口、ASR/翻译协调
├── core/
│   ├── audio_capture.py     # Windows 系统声音回环采集
│   ├── stt_engine.py        # faster-whisper 语音识别与断句
│   └── translator.py        # Ollama 翻译及短句批处理
├── ui/
│   └── overlay.py           # PyQt6 悬浮字幕窗口
├── models/                  # 本地 Whisper 模型（不提交）
├── requirements.txt
├── run.bat
└── build.py                 # Windows 打包脚本
```

## 打包

```bash
python build.py
```

构建产物位于 `dist/`。模型文件通常不随可执行文件打包，需要在发布包中单独提供或由用户准备。

## 从其他目录启动

程序会根据源码文件位置定位 `models/`，不要求当前终端目录固定为项目根目录。推荐使用项目根目录中的 `run.bat` 启动；打包后也请将 `models/kotoba-whisper-v2/` 放在程序目录下的 `models/` 中。

## 常见问题

### 中文字幕没有出现

- 确认 Ollama 正在运行；
- 确认已执行 `ollama pull hy-mt2-1.8b`；
- 在终端查看 Ollama 和程序日志；
- 确认模型名与 `main.py` 中的配置一致。

### 日文识别为空或明显错误

- 确认 `models/kotoba-whisper-v2/model.bin` 存在；
- 确认捕获到的是目标影片声音而不是麦克风；
- 提高影片音量并关闭过强的系统降噪；
- 使用 NVIDIA GPU 以降低实时识别积压。

### 运行时报 CUDA 或 DLL 错误

检查 NVIDIA 驱动、CUDA/cuDNN 与 CTranslate2 的兼容性；也可以先改为 CPU 模式验证功能链路。

## 许可证与责任

请在发布前补充适合你的开源许可证文件（例如 `LICENSE`）。本项目作者不对用户使用本软件产生的版权、隐私、法律或平台规则问题承担责任。
