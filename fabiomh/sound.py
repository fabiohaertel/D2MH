"""Drop tracker alert sound: a bell "ting", synthesized in memory (nothing is written to disk, no .wav file).

- winsound only plays in-memory WAV synchronously (SND_MEMORY does not accept SND_ASYNC). That is why each sound runs in
  a daemon thread, so as not to stall the main loop. A new sound cuts off the previous one.
- Without an audio device, PlaySound raises RuntimeError: the drop still alerts through the banner and the marker, and
  the reason shows up in the log with DEBUG_LOG.
- Speech (drops.DROP_SPEAK): Windows voice (SAPI) through pywin32, in a daemon thread of its own, which also owns the
  COM object. The loop only puts the name in a short queue. With the queue full, the name is discarded: many items at
  once do not turn into minutes of delayed speech, and the banner and the marker still alert. If SAPI fails, the "ting"
  plays.
- Measured (in-memory synthesis): importing win32com takes ~640 ms cold, so it stays at the top of the module, at
  startup. Creating the voice takes ~10 ms and synthesizing a name 7 to 21 ms, both in the speech thread.
"""
import io
import math
import queue
import struct
import threading
import wave
import winsound

from drops import DROP_SPEAK, DROP_SPEECH_RATE, DROP_SPEECH_VOICE
from fabiomh.log import report

if DROP_SPEAK:
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as import_error:
        pythoncom = None
        report("som", f"sem pywin32, a fala vira \"ting\": {import_error}")

SAMPLE_RATE = 44100
DURATION_SECONDS = 0.6
VOLUME = 0.5           # from 0 to 1
ATTACK_SECONDS = 0.002  # fast rise, so the start of the sound does not click
DECAY = 7              # the higher, the shorter the "ting"

# (frequency in Hz, weight): the main note and the harmonics that give the bell timbre
PARTIALS = ((1760, 1.0), (2640, 0.45), (4400, 0.2))


def build_ting_wav():
    """Returns the bytes of a 16-bit mono WAV."""
    total_weight = sum(weight for _, weight in PARTIALS)
    samples = []

    for i in range(int(SAMPLE_RATE * DURATION_SECONDS)):
        t = i / SAMPLE_RATE
        envelope = min(t / ATTACK_SECONDS, 1) * math.exp(-DECAY * t)
        wave_value = sum(weight * math.sin(2 * math.pi * freq * t) for freq, weight in PARTIALS) / total_weight
        samples.append(int(32767 * VOLUME * envelope * wave_value))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buffer.getvalue()


TING_WAV = build_ting_wav()


def play_wav(wav_bytes):
    try:
        winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
    except RuntimeError as error:
        report("som", f"não tocou: {error}")


def play_ting():
    """Plays without blocking the caller."""
    threading.Thread(target=play_wav, args=(TING_WAV,), daemon=True).start()


SPEECH_QUEUE_SIZE = 5
SVSF_IS_NOT_XML = 16  # SAPI does not interpret the item name as markup
speech_queue = queue.Queue(SPEECH_QUEUE_SIZE)


def create_voice():
    """Only in the speech thread: the COM object belongs to the thread that created it."""
    pythoncom.CoInitialize()
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    voice.Rate = DROP_SPEECH_RATE

    for candidate in voice.GetVoices():
        if DROP_SPEECH_VOICE.lower() in candidate.GetDescription().lower():
            voice.Voice = candidate
            return voice
    report("som", f"voz {DROP_SPEECH_VOICE!r} não encontrada; usando a padrão do Windows")
    return voice


def speech_worker():
    voice = None
    try:
        if pythoncom:
            voice = create_voice()
    except Exception as error:
        report("som", f"SAPI não iniciou, a fala vira \"ting\": {error}")

    while True:
        text = speech_queue.get()
        if voice:
            try:
                voice.Speak(text, SVSF_IS_NOT_XML)
                continue
            except Exception as error:
                report("som", f"não falou {text!r}: {error}")
        play_wav(TING_WAV)


def speak(text):
    """Speaks without blocking the caller. With the queue full, discards."""
    try:
        speech_queue.put_nowait(text)
    except queue.Full:
        pass


if DROP_SPEAK:
    threading.Thread(target=speech_worker, daemon=True).start()
