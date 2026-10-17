# CastVox · AI Voiceovers & Multi-Character Dubbing

**Turn a script into editable dialogue and narration with your AI agent. Compare voices first, then produce the audio.**

CastVox is a local-first **agent skill for text-to-speech (TTS), voiceovers, and multi-character dubbing**. Its project workflow uses MiniMax CN and works with local coding agents including Codex and Claude Code, with adapters for Kimi Work, Doubao Work, and WorkBuddy.

[简体中文](README.md) · [Quick start](#quick-start) · [Example workflow](#example-workflow) · [Compatibility](#compatibility) · [Report an issue](https://github.com/Ace199/CastVox-Skill/issues)

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Voice provider: MiniMax](https://img.shields.io/badge/Voice-MiniMax-4055C8)
![Local-first](https://img.shields.io/badge/Workflow-Local--first-2D7A65)

## What does it do?

Choosing voices is only part of a dubbing task. You also need to compare auditions, keep characters consistent, review performance, and organize files for editing. CastVox helps your agent handle that workflow in one conversation.

- **Find a voice for each character.** Receive 2–3 verified candidates, then choose which auditions to generate.
- **Use voices you already have.** Reuse project voices, saved defaults, or explicit voice IDs.
- **Review before generating.** See the text, supported settings, provider/model, and request scope before paid synthesis.
- **Reuse matching recordings.** Regenerate changed lines while keeping verified audio that still matches the final performance.
- **Keep editing assets.** Get individual WAV files, available SRT subtitles, a merged listening copy, performance notes, and a file index.
- **Keep earlier versions.** Voice changes and dialogue revisions produce new deliveries without replacing the old audio.

Useful for short dramas, audio stories, video narration, and scripted character conversations. Local state and files remain on your computer; synthesis text is sent to the selected voice service. Provider fees apply.

## Example workflow

After installing the skill, paste this prompt into your agent and add a script:

```text
Use soundmaker-dubbing to voice this script.
Analyze the characters and recommend 2–3 suitable voices for each.
Let me choose which auditions to generate. Compare candidates using
one original line per character with the same performance settings.
After I choose, review the final lines and paid request scope with me.
Deliver a merged listening copy, individual WAV clips, and real subtitles
where available. Reuse auditions only if they match the final performance.
```

No script yet? Start with: “Write a short conversation between three people discussing Macbeth. I need dubbing; draft the script first, then let me choose a voice workflow.”

The following is a workflow illustration, not an audio demo:

```text
You:    Dub this three-character script.
Agent:  Use your own voices, or get recommendations?
You:    Recommend two candidates for each character.
Agent:  Shows names, IDs, differences, and audition choices.
You:    Audition all of them.
Agent:  Reviews the comparison lines and request scope before generation.
You:    I've chosen the voices. Continue with the full script.
Agent:  Reuses matching auditions and generates the remaining lines.
You:    Make the gap after the second line longer.
Agent:  Adjusts the local merge and saves a new version.
```

### Three entry points

| Route | When to use it |
|---|---|
| **Use my voices** | You already have project bindings, defaults, or provider voice IDs. |
| **Recommend voices** | You want character matching, side-by-side auditions, and a reusable project voice library. |
| **Use the app's built-in audio tool** | Offered only when the current Kimi/Doubao session exposes an actual callable audio tool. |

The first two routes open the local **Voice Studio** only when you want to manage voices or edit bindings. It supports Chinese and English. The built-in route delivers the tool's actual audio or links, does not add voices to the project library, and does not promise consistent voices across calls.

MiniMax lists available voices; the agent performs the character matching. Recommendations and voice-library updates do not themselves trigger paid synthesis.

## Quick start

For the project voice workflow, you need a local-command-capable agent, **Python 3.11+**, and a working **MiniMax CN API configuration**. Most live host verification has been on Windows.

### 1. Clone the repository

```powershell
git clone https://github.com/Ace199/CastVox-Skill.git
cd CastVox-Skill
python -m makesound.media
```

The core Python runtime uses only the standard library. The media check does not call a voice provider or install software. Compatible mono PCM WAV files can be handled without FFmpeg; MP3 encoding and resampling require existing media tools.

### 2. Install the skill

Link `skills/soundmaker-dubbing/` into your agent's skill directory, then reload skills or start a new conversation. For **Codex on Windows**, run this from the repository root when the destination does not already exist:

```powershell
$skillSource = (Resolve-Path './skills/soundmaker-dubbing').Path
$skillParent = Join-Path $env:USERPROFILE '.codex/skills'
New-Item -ItemType Directory -Path $skillParent -Force | Out-Null
New-Item -ItemType Junction -Path (Join-Path $skillParent 'soundmaker-dubbing') -Target $skillSource
```

Claude Code uses `~/.claude/skills`; WorkBuddy uses `~/.workbuddy/skills`. Kimi/Doubao paths depend on the host version. Check and back up existing installations before replacing them. The [installation guide](docs/usage.md#安装为目录链接) includes host paths, runtime-location setup, and troubleshooting; this detailed guide is currently in Chinese.

### 3. Configure the voice service and try a script

Ask your agent:

> Use soundmaker-dubbing to recommend voices. If MiniMax is not configured, open the local configuration file so I can enter my API Key. Show me the audition plan before generating anything.

The local configuration lives at `~/.config/minimax/config.json`. Enter your real API Key locally rather than pasting it into chat. Save it, let the agent check the configuration, then use the example prompt above.

## Deliverables

The project voice workflow keeps readable output together:

```text
Your project/
├─ 配音/<task title>/
│  ├─ 文件索引.md                 # File index
│  ├─ 试听/                      # Individual voice auditions
│  └─ v01_初版/
│     ├─ 合并试听_全文.wav         # Merged listening copy
│     ├─ 配音演绎单.md             # Actual performance record
│     ├─ 交付说明.md               # Delivery status and notes
│     ├─ 剧本.md                   # Script
│     └─ 分句/                    # Individual WAV clips and available SRTs
└─ .makesound/                    # Internal state, inputs, cache, and receipts
```

The folder names above reflect the current documented layout. Changed emotion, voice, or vocal controls can require new synthesis. Changed gaps between lines are handled locally. Missing subtitles are reported separately; the tool does not invent timestamps, create empty subtitles as a success placeholder, or automatically resynthesize audio to repair them.

## Compatibility

| Agent / service | Current scope |
|---|---|
| [Codex](skills/soundmaker-dubbing/references/harnesses/codex.md) | Original-chat wake-up has been observed; queued does not mean processing is complete. |
| [Claude Code](skills/soundmaker-dubbing/references/harnesses/claude.md) | Binding recovery tested on Windows 2.1.295. |
| [Kimi Work](skills/soundmaker-dubbing/references/harnesses/kimi.md) | Binding/resumption tested on Windows 3.2.8; regular Chat and standalone CLI are separate environments. |
| [Doubao Work](skills/soundmaker-dubbing/references/harnesses/doubao.md) | Binding recovery tested on Windows 2.32.5; requires the current instance's local bridge configuration. |
| [WorkBuddy](skills/soundmaker-dubbing/references/harnesses/workbuddy.md) | Managed waiting/return path implemented; full live desktop workflow still needs verification. |
| **MiniMax CN** | Real synthesis adapter implemented. Supported models and controls are documented in the [provider reference](skills/soundmaker-dubbing/references/minimax.md). |
| **Volcengine** | Configuration management only; synthesis is not implemented. |

Host updates and permissions can affect resumption. Saved bindings remain available if a notification fails; return to the original conversation and say the binding is complete. Cross-platform and all-version recovery are not fully verified.

## Questions and contributions

For a non-billable development walkthrough, FakeProvider exercises the local binding/recovery/delivery path with **test silence**, not real voice audio. Actual auditions and production calls use the configured provider and require the relevant authorization.

[Usage guide](docs/usage.md) · [Architecture](docs/architecture.md) · [Voice Studio development](web/README.md) · [Issues](https://github.com/Ace199/CastVox-Skill/issues)

When reporting a problem, include your agent/version, the failing step, expected versus actual behavior, and redacted error details. Do not include API Keys, private receipts, or signed download URLs. Supporting technical documentation is currently primarily in Chinese.

If CastVox helps your workflow, star the repository to find it again, or share it with someone making dialogue, narration, or audio stories.
