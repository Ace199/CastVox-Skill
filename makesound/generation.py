"""Frozen sentence chunks, opt-in providers, local exports and restart-safe execution."""
import copy
import os
import wave

from . import validation as v
from .core_v16 import uid
from .errors import MakeSoundError, require
from .providers import FakeProvider, adapter_for, duration, performance_directives
from .storage import atomic_write, digest, file_lock, read_json
from .inline_controls import request_text
from .media import MediaTools


def seal(obj):
    return {**obj, "snapshot_hash": digest(obj)}


class Generation:
    def __init__(self, core, fake=None, *, minimax=None, media=None, output_format=None):
        self.core = core
        self.fake = fake if fake is not None else FakeProvider()
        self.minimax = minimax
        self.media = media or MediaTools()
        require(output_format in {None, 'wav', 'mp3'}, 'export_not_implemented', 'Unsupported task output format.')
        self.output_format = output_format

    def freeze(self, segments, *, confirmed=False, authorized=False):
        return self._freeze(segments, confirmed=confirmed, authorized=authorized)

    def freeze_from_answer(self, question_id, harness_session_id, segments, *, confirmed=False, authorized=False, job_id=None):
        from .questions import Questions
        v.identifier(harness_session_id)
        question = Questions(self.core).read(question_id)
        require(question["status"] == "answered" and question["claimed_by"] == harness_session_id
                and question["harness_session_id"] == harness_session_id,
                "answer_not_claimed", "Harness must claim this answer before freezing its Job.")
        if job_id is not None:
            v.identifier(job_id)
        return self._freeze(segments, confirmed=confirmed, authorized=authorized,
                            answer=question["answer"], job_id=job_id or question["job_id"])

    def _freeze(self, segments, *, confirmed, authorized, answer=None, job_id=None):
        require(confirmed is True and authorized is True, "authorization_required", "Confirmed text and task authorization are required.")
        require(isinstance(segments, list) and 0 < len(segments) <= 10000)
        preset = self.core.read()
        settings = copy.deepcopy(preset["project_settings"])
        if self.output_format is not None:
            settings['audio_format'] = self.output_format
        require(settings["audio_format"] in {'wav', 'mp3'} and settings["subtitle_type"] == "sentence",
                "export_not_implemented", "Only WAV/MP3 and sentence subtitles are implemented.")
        if settings['audio_format'] == 'mp3':
            self.media.require_available()
        chunks = []
        for index, segment in enumerate(segments):
            v.shape(segment, {"paragraph_id", "sentence_id", "text", "role_id", "project_voice_id", "gender", "settings", "pause_ms", "fake_duration_seconds", "provider_directives", "inline_controls"},
                    {"paragraph_id", "sentence_id", "text"})
            for field in ("paragraph_id", "sentence_id"):
                v.identifier(segment[field])
            require(isinstance(segment["text"], str) and 0 < len(segment["text"]) <= 100000)
            if answer is not None:
                role = segment.get("role_id")
                require(role in answer["resolved"], "missing_roles", "Segment must reference an answered role.")
                require(not any(key in segment for key in ("project_voice_id", "gender", "settings")),
                        "answer_conflict", "Answered bindings cannot be overridden while freezing the Job.")
                resolved = copy.deepcopy(answer["resolved"][role])
            else:
                resolved = self.core.resolve(segment.get("project_voice_id"), segment.get("gender"), segment.get("settings"), preset=preset)
            require(resolved["status"] == "ready", "needs_question", "A project voice must be selected.")
            performance_directives(resolved['source'], segment.get('provider_directives'))
            request_text({**segment, 'source': resolved['source']})
            seconds = segment.get("fake_duration_seconds", 6.0)
            require(type(seconds) in (int, float) and .001 <= seconds <= 120)
            require(resolved["source"]["provider"] == "fake" or "fake_duration_seconds" not in segment,
                    "invalid_data", "Fake timing is only valid for Fake Provider.")
            pause = segment.get("pause_ms", 0)
            require(type(pause) is int and 0 <= pause <= 99990)
            chunks.append({**copy.deepcopy(segment), **{k: val for k, val in resolved.items() if k != "status"},
                           "chunk_id": f"chunk_{index:06d}", "pause_ms": pause, "fake_duration_seconds": seconds})
        require(len({c["sentence_id"] for c in chunks}) == len(chunks), message="Sentence IDs must be unique.")
        # A paragraph is contiguous in manuscript order; never reorder repeated IDs.
        seen = set()
        previous = None
        for chunk in chunks:
            paragraph = chunk["paragraph_id"]
            if paragraph != previous:
                require(paragraph not in seen, message="Paragraph segments must be contiguous.")
                seen.add(paragraph)
            previous = paragraph
        snapshot = seal({"schema_version": "1.6", "project_id": preset["project_id"], "revision": preset["revision"],
                         "job_id": job_id or uid("job_"), "segments": copy.deepcopy(segments), "chunks": chunks,
                         "project_settings": copy.deepcopy(settings), "confirmed": True, "authorized": True})
        v.no_secrets(snapshot)
        path = self.core.managed_path(f".makesound/jobs/{snapshot['job_id']}/snapshot.json")
        with file_lock(path.with_suffix(".lock")):
            require(not path.exists(), "already_exists", "Frozen Job cannot be overwritten.")
            atomic_write(path, snapshot)
        return snapshot

    def load(self, jid):
        v.identifier(jid)
        obj = read_json(self.core.managed_path(f".makesound/jobs/{jid}/snapshot.json"))
        require(obj.get("snapshot_hash") == digest({k: val for k, val in obj.items() if k != "snapshot_hash"}),
                "snapshot_corrupt", "Frozen Job integrity failed.")
        require(obj["job_id"] == jid and obj["project_id"] == self.core.read()["project_id"], "project_mismatch", "Job identity differs.")
        return obj

    def run(self, jid, *, retry_failed=False, retry_local=False):
        v.identifier(jid)
        folder = self.core.managed_path(f".makesound/jobs/{jid}")
        with file_lock(folder / "execution.lock"):
            snap = self.load(jid)
            if snap['project_settings']['audio_format'] == 'mp3':
                self.media.require_available()
            if self.minimax is not None:
                self.minimax.bind(snap, folder)
            state_path = folder / "state.json"
            state = read_json(state_path) if state_path.exists() else {"job_id": jid, "chunks": {}}
            for chunk in snap["chunks"]:
                cid = chunk["chunk_id"]
                old = state["chunks"].get(cid, {})
                if old.get("status") in {"running", "billing_unknown"}:
                    continue  # Crash after dispatch is uncertain, never a blind retry.
                if old.get("status") == "failed" and not retry_failed:
                    continue
                if old.get('status') == 'repair_required' and not retry_local:
                    continue
                if old.get("status") == "success":
                    try:
                        path = self.core.managed_path(old["path"])
                        if digest(path.read_bytes().hex()) == old["audio_hash"] and duration(path) == old["duration_seconds"]:
                            continue
                    except (OSError, MakeSoundError, KeyError):
                        pass
                    if chunk['source']['provider'] != 'fake':
                        state['chunks'][cid] = {**old, 'status': 'repair_required', 'error': 'artifact_repair_required'}
                        atomic_write(state_path, state)
                        if not retry_local:
                            continue
                # Cache is content-based, with source, actual settings, text, pause and timing.
                key = digest({**{k: chunk[k] for k in ("source", "effective_settings", "text", "pause_ms", "fake_duration_seconds")}, **{k: chunk[k] for k in ("provider_directives", "inline_controls") if chunk.get(k)}})
                relative = f".makesound/cache/{key}.wav"
                target = self.core.managed_path(relative)
                cache_meta = target.with_suffix(".json")
                try:
                    cache_hit = False
                    with file_lock(target.with_suffix(".lock")):
                        if target.exists() and cache_meta.exists():
                            try:
                                cached = read_json(cache_meta)
                                cache_hit = cached["audio_hash"] == digest(target.read_bytes().hex()) and duration(target) == cached["duration_seconds"]
                            except (MakeSoundError, KeyError, OSError):
                                cache_hit = False
                        if cache_hit:
                            metadata = {k: cached[k] for k in ('speech_seconds', 'duration_seconds', 'subtitles', 'subtitle_status', 'timing_source', 'subtitle_error') if k in cached}
                        else:
                            provider = adapter_for(chunk["source"], self.fake, self.minimax)
                            if chunk['source']['provider'] != 'fake' and (target.exists() or cache_meta.exists()):
                                require(retry_local, 'artifact_repair_required', 'Restore local audio before another provider request.')
                            state["chunks"][cid] = {"status": "running"}
                            atomic_write(state_path, state)
                            temporary = target.with_suffix(".tmp")
                            try:
                                metadata = (provider.synthesize(chunk, temporary, recovery_only=retry_local)
                                            if chunk['source']['provider'] == 'minimax' else provider.synthesize(chunk, temporary))
                                require(duration(temporary) == metadata["duration_seconds"], "invalid_audio", "Provider audio failed validation.")
                                os.replace(temporary, target)
                            finally:
                                temporary.unlink(missing_ok=True)
                            atomic_write(cache_meta, {**metadata, "audio_hash": digest(target.read_bytes().hex())})
                    state["chunks"][cid] = {"status": "success", "path": relative, "cache_hit": cache_hit,
                                              "audio_hash": digest(target.read_bytes().hex()), **metadata}
                except MakeSoundError as exc:
                    safe = exc.code in {'safe_retry', 'provider_not_implemented', 'authorization_required', 'authorization_limit',
                                        'config_missing', 'invalid_credentials', 'invalid_region', 'invalid_base_url', 'region_mismatch',
                                        'model_not_configured', 'text_limit', 'parameter_unverified', 'media_tools_missing', 'provider_region_unverified'}
                    status = 'repair_required' if exc.code == 'artifact_repair_required' else 'failed' if safe else 'billing_unknown'
                    state["chunks"][cid] = {"status": status, "error": exc.code}
                except Exception:
                    # The adapter outcome cannot be inferred from an unexpected local error.
                    state["chunks"][cid] = {"status": "billing_unknown", "error": "execution_interrupted"}
                atomic_write(state_path, state)
            state["status"] = "success" if all(r["status"] == "success" for r in state["chunks"].values()) else "incomplete"
            if state["status"] == "success":
                try:
                    state["exports"] = self._export(snap, state["chunks"], folder)
                    state.pop('export_error', None)
                except MakeSoundError as exc:
                    state['status'] = 'export_incomplete'
                    state['export_error'] = exc.code
                    state.pop('exports', None)
                except Exception:
                    state['status'] = 'export_incomplete'
                    state['export_error'] = 'local_export_failed'
                    state.pop('exports', None)
            try:
                self.core.capture_preview(snap, state["chunks"])
                state["preview_status"] = "checked"
            except Exception:
                state["preview_status"] = "failed"  # Ancillary work cannot fail synthesis.
            atomic_write(state_path, state)
            return state

    def export_existing(self, jid):
        v.identifier(jid)
        folder = self.core.managed_path(f'.makesound/jobs/{jid}')
        with file_lock(folder / 'execution.lock'):
            snap = self.load(jid)
            state_path = folder / 'state.json'
            state = read_json(state_path)
            for chunk in snap['chunks']:
                result = state['chunks'].get(chunk['chunk_id'], {})
                require(result.get('status') == 'success', 'artifact_repair_required', 'All source chunks must be successful before local export.')
                path = self.core.managed_path(result['path'])
                require(digest(path.read_bytes().hex()) == result['audio_hash'] and duration(path) == result['duration_seconds'],
                        'artifact_repair_required', 'Restore source audio before local export.')
            try:
                state['exports'] = self._export(snap, state['chunks'], folder)
                state['status'] = 'success'
                state.pop('export_error', None)
            except MakeSoundError as exc:
                state['status'] = 'export_incomplete'
                state['export_error'] = exc.code
                state.pop('exports', None)
            atomic_write(state_path, state)
            return state

    def _export(self, snap, results, folder):
        groups = {}
        mode = snap["project_settings"]["export_mode"]
        for chunk in snap["chunks"]:
            group = "whole" if mode == "whole" else chunk["paragraph_id"] if mode == "paragraph" else chunk["sentence_id"]
            groups.setdefault(group, []).append(chunk)
        exports = []
        output_folder = self.core.output_path(f".makesound/exports/audio/{snap['job_id']}")
        output_folder.mkdir(parents=True, exist_ok=True)
        for group, chunks in groups.items():
            target = output_folder / (group + ".wav")
            temporary = target.with_suffix(".wav.tmp")
            subtitles = []
            elapsed = 0
            export_rate = 32000 if any(c['source']['provider'] != 'fake' for c in chunks) else 8000
            cleanup = []
            try:
                with wave.open(str(temporary), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(export_rate)
                    for i, chunk in enumerate(chunks, 1):
                        result = results[chunk["chunk_id"]]
                        original = self.core.managed_path(result['path'])
                        with wave.open(str(original), 'rb') as audio:
                            rate = audio.getframerate()
                        if rate != export_rate:
                            converted = folder / (chunk['chunk_id'] + '.export.tmp.wav')
                            cleanup.append(converted)
                            self.media.convert(original, converted, format='wav', rate=export_rate)
                            original = converted
                        with wave.open(str(original), "rb") as audio:
                            require((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, export_rate), "invalid_audio", "Incompatible chunk encoding.")
                            output.writeframes(audio.readframes(audio.getnframes()))
                        if snap['project_settings']['subtitle_enabled']:
                            if chunk['source']['provider'] == 'fake':
                                rows = [{'start': 0, 'end': result['speech_seconds'], 'text': chunk['text']}]
                            else:
                                require(result.get('subtitle_status') == 'verified_timing' and result.get('subtitles'),
                                        'subtitle_unavailable', 'Audio was saved; verified sentence timing is required before SRT export.')
                                from .minimax_provider import normalize_subtitles
                                rows = normalize_subtitles([{'text': r['text'], 'time_begin': r['start'] * 1000,
                                                             'time_end': r['end'] * 1000} for r in result['subtitles']],
                                                           chunk['text'], result['speech_seconds'])
                            for row in rows:
                                subtitles.append(f"{len(subtitles) + 1}\n{timestamp(elapsed + row['start'])} --> {timestamp(elapsed + row['end'])}\n{row['text']}\n")
                        elapsed += result["duration_seconds"]
                require(abs(duration(temporary) - elapsed) < .001, "invalid_audio", "Final measured duration differs from chunk timing.")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
                for converted in cleanup:
                    converted.unlink(missing_ok=True)
            entry = {"audio": target.relative_to(self.core.root).as_posix(), "duration_seconds": elapsed}
            if snap['project_settings']['audio_format'] == 'mp3':
                mp3 = target.with_suffix('.mp3')
                temp_mp3 = target.with_suffix('.mp3.tmp')
                try:
                    metadata = self.media.convert(target, temp_mp3, format='mp3', rate=32000)
                    require(metadata['codec'] == 'mp3' and abs(metadata['duration_seconds'] - elapsed) < .15,
                            'invalid_audio', 'MP3 duration differs from the measured PCM timeline.')
                    os.replace(temp_mp3, mp3)
                finally:
                    temp_mp3.unlink(missing_ok=True)
                entry.update(audio=mp3.relative_to(self.core.root).as_posix(), pcm_audio=entry['audio'],
                             encoded_duration_seconds=metadata['duration_seconds'])
            if snap["project_settings"]["subtitle_enabled"]:
                srt = output_folder / (group + ".srt")
                temp = srt.with_suffix(".srt.tmp")
                try:
                    temp.write_text("\n".join(subtitles), encoding="utf-8")
                    os.replace(temp, srt)
                finally:
                    temp.unlink(missing_ok=True)
                entry["subtitle"] = srt.relative_to(self.core.root).as_posix()
            exports.append(entry)
        return exports


def timestamp(seconds):
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
