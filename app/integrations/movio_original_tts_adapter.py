"""Strict adapter for the user's original TTS_DEMO(3).ipynb optimized MOVIO synthesis.
No default DhVaani TTS call, no Whisper, no fallback voices.
"""
import io
import wave
import numpy as np

class OriginalMovioTTS:
    def __init__(self, namespace):
        self.ns=namespace
        required=['movio_stream_response','smooth_join_audio','prepare_movio_request',
                  'ENGLISH_PROMPT_CACHE','TAMIL_PROMPT_CACHE','model']
        missing=[k for k in required if k not in namespace or namespace[k] is None]
        if missing:
            raise RuntimeError('Your original MOVIO TTS pipeline is not ready: '+', '.join(missing))
        self.synthesize=self._synthesize
    def _synthesize(self,text,group):
        group=group.upper()
        if group not in ('ENGLISH','TAMIL','TANGLISH'):
            raise ValueError('Invalid MOVIO TTS language: '+group)
        events=list(self.ns['movio_stream_response'](text,group))
        if not events:raise RuntimeError('Your MOVIO pipeline returned no audio')
        sr=int(events[0].get('sample_rate',self.ns.get('SAMPLING_RATE',24000)))
        parts=[np.asarray(e['audio'],dtype=np.float32).reshape(-1) for e in events]
        audio=np.asarray(self.ns['smooth_join_audio'](parts,sr=sr,fade_ms=10),dtype=np.float32).reshape(-1)
        if not audio.size:raise RuntimeError('Your MOVIO pipeline returned empty audio')
        peak=float(np.max(np.abs(audio)))
        if peak>0.95:audio=audio*(0.95/peak)
        out=io.BytesIO()
        with wave.open(out,'wb') as wf:
            wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(sr)
            wf.writeframes((np.clip(audio,-1,1)*32767).astype(np.int16).tobytes())
        return out.getvalue()
