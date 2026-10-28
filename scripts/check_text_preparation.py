"""Exercise shared text preparation without loading TTS or Qwen weights."""
from pathlib import Path
import contextlib
import io
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = (ROOT / 'runtime/stages/02_speech.py').read_text().split('# ---- Source section 39 ----')[0]
    ns = dict(__name__='movio_text_fixture', FIRST_MIN_WORDS=2, FIRST_TARGET_WORDS=2,
              FIRST_MAX_WORDS=3, NEXT_MIN_WORDS=3, NEXT_TARGET_WORDS=5, NEXT_MAX_WORDS=8,
              KEEP_WHOLE_IF_WORDS_LE=4, ENGLISH_SINGLE_CHUNK_WORDS=10, ENGLISH_MIN_CHUNK_WORDS=4)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(source, '<shared speech text>', 'exec'), ns)
    cases = [('ENGLISH', 'Your cab from Chennai Central to Tambaram is booked.'),
             ('TAMIL', 'சென்னை சென்ட்ரலில் இருந்து தாம்பரம் செல்ல வேண்டும்.'),
             ('TANGLISH', 'Vanakkam unga cab booking confirm pannalama?')]
    for group, text in cases:
        with contextlib.redirect_stdout(io.StringIO()):
            result = ns['prepare_movio_request'](text, group)
        assert isinstance(result, dict) and result.get('chunks'), group
        assert all(isinstance(chunk, str) and chunk.strip() for chunk in result['chunks']), group
    print(json.dumps({'passed': True, 'cases': len(cases),
                      'scope': 'Text preparation returns usable chunks in three modes; not a pronunciation/listening test.'}, indent=2))


if __name__ == '__main__':
    main()
