"""Transcribing a recording on this computer with Whisper (faster-whisper), free and private.
The Hebrew model of ivrit.ai is downloaded once (about 1.6 GB) and kept on the computer."""
import os
import time

from .log import log

MODELS = {
    "ivrit-ai": ("ivrit-ai/whisper-large-v3-turbo-ct2", "עברית מדויקת (ivrit.ai) — מומלץ, 1.6GB"),
    "large-v3-turbo": ("large-v3-turbo", "Whisper large-v3-turbo רגיל — 1.6GB"),
    "small": ("small", "קטן ומהיר, פחות מדויק — 0.5GB"),
}

_loaded = {}


def available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _fix_av():
    """faster-whisper opens recordings with av.open(..., metadata_errors=...), a parameter that
    newer versions of PyAV no longer take: without it the recording opens all the same."""
    import av
    if getattr(av.open, "_rav_fixed", False):
        return
    orig = av.open

    def open_(*a, **k):
        try:
            return orig(*a, **k)
        except TypeError:
            if k.pop("metadata_errors", None) is None:
                raise
            return orig(*a, **k)
    open_._rav_fixed = True
    av.open = open_


def _model(key):
    if key in _loaded:
        return _loaded[key]
    from faster_whisper import WhisperModel
    name = MODELS.get(key, MODELS["ivrit-ai"])[0]
    log(f"טוען את מודל התמלול {name} (בפעם הראשונה הוא יורד מהאינטרנט — זה לוקח זמן)…")
    m = None
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            m = WhisperModel(name, device="cuda", compute_type="int8_float16")
            log("התמלול ירוץ על כרטיס המסך")
    except Exception as e:
        log(f"כרטיס המסך לא זמין לתמלול ({e}), ממשיך במעבד")
        m = None
    if m is None:
        # all the processor's cores (the model takes only 4 unless told)
        m = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=max(4, os.cpu_count() or 4))
        log(f"התמלול ירוץ במעבד, על {max(4, os.cpu_count() or 4)} ליבות")
    _loaded[key] = m
    return m


def torah_prompt(rav="", topic=""):
    """A few words the model is given before it starts: the rabbi, the subject and some Torah terms
    (kept short: the model takes only a little, and a long prompt made the transcription fail)."""
    head = f"{rav}, {topic}. " if rav else ""
    return (head + "גמרא, רש\"י, תוספות, רמב\"ם, הלכה, מדרש, הקב\"ה, מצווה, חז\"ל.")[:160]


def transcribe(path, key="ivrit-ai", progress=None, should_stop=None, prompt="", fast=True):
    """The text of the recording at path, in paragraphs. prompt: words the model is given first
    (see torah_prompt)."""
    _fix_av()
    model = _model(key)
    try:
        return _transcribe(model, path, prompt, progress, should_stop, fast)
    except InterruptedError:
        raise
    except Exception as e:
        if fast:
            log(f"התמלול המהיר נכשל ({str(e)[:80]}) — מתמלל בדרך הרגילה")
            try:
                return _transcribe(model, path, prompt, progress, should_stop, False)
            except InterruptedError:
                raise
            except Exception as e2:
                e = e2
        if not prompt:
            raise e
        log(f"התמלול עם רשימת המונחים נכשל ({str(e)[:80]}) — מתמלל בלעדיה")
        return _transcribe(model, path, "", progress, should_stop, False)


_batched = {}


def _transcribe(model, path, prompt, progress, should_stop, fast=True):
    """fast: the recording cut into pieces that are transcribed together, taking the first guess for
    every word (about 2–3 times faster). Otherwise: one piece after the other, weighing 5 guesses."""
    extra = {"initial_prompt": prompt} if prompt else {}
    if fast:
        from faster_whisper import BatchedInferencePipeline
        pipe = _batched.setdefault(id(model), BatchedInferencePipeline(model))
        segments, info = pipe.transcribe(path, language="he", vad_filter=True, beam_size=1, batch_size=8, **extra)
    else:
        segments, info = model.transcribe(path, language="he", vad_filter=True, beam_size=5,
                                          condition_on_previous_text=False, **extra)
    total = info.duration or 0
    log(f"מתמלל {total / 60:.0f} דקות הקלטה…")
    paras, cur, last_end, t0, shown = [], [], 0.0, time.time(), 0
    for seg in segments:
        if should_stop and should_stop():
            raise InterruptedError("נעצר")
        text = seg.text.strip()
        if not text:
            continue
        # a pause of more than 2.5 seconds, or a long paragraph, starts a new paragraph
        if cur and (seg.start - last_end > 2.5 or sum(len(c) for c in cur) > 900):
            paras.append(" ".join(cur))
            cur = []
        cur.append(text)
        last_end = seg.end
        if total and progress and seg.end - shown > 30:
            shown = seg.end
            el = time.time() - t0
            left = el / seg.end * (total - seg.end) if seg.end else 0
            progress(f"תמלול {seg.end / total:.0%} (נשארו בערך {left / 60:.0f} דקות)")
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)
