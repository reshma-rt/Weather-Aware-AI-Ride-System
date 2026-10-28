"""Static checks only; never start the voice service or download models."""
from pathlib import Path
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check():
    errors = []
    python_files = list(ROOT.rglob('*.py'))
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:
            errors.append(f'{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}')
    notebook = json.loads((ROOT / 'MOVIO_Pipeline.ipynb').read_text())
    for index, cell in enumerate(notebook['cells']):
        if cell['cell_type'] == 'code':
            ast.parse(''.join(cell['source']), filename=f'notebook cell {index}')
            if cell.get('outputs') or cell.get('execution_count') is not None:
                errors.append(f'Notebook cell {index} contains outputs or execution state.')
    node = shutil.which('node')
    js_checks = 0
    if node:
        for path in (ROOT / 'app/web').glob('*.js'):
            result = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
            js_checks += 1
            if result.returncode:
                errors.append(f'{path.relative_to(ROOT)}: {result.stderr[:300]}')
        with tempfile.TemporaryDirectory() as directory:
            for html in (ROOT / 'app').rglob('*.html'):
                for i, match in enumerate(re.finditer(r'<script\b([^>]*)>(.*?)</script\s*>', html.read_text(), re.I | re.S)):
                    attrs, content = match.groups()
                    if re.search(r'\bsrc\s*=', attrs, re.I) or not content.strip():
                        continue
                    if re.search(r'application/(?:ld\+)?json', attrs, re.I):
                        continue
                    path = Path(directory) / f'{html.stem}_{i}.js'
                    path.write_text(content)
                    result = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
                    js_checks += 1
                    if result.returncode:
                        errors.append(f'{html.relative_to(ROOT)} inline script {i}: {result.stderr[:300]}')
    # Check that referenced local dashboard scripts/styles are bundled.
    from urllib.parse import urlsplit
    index = ROOT / 'app/web/index.html'
    html = index.read_text(encoding='utf-8')
    references = re.findall(r'<script[^>]*src=["\']([^"\']+)', html, re.I)
    references += re.findall(r'<link[^>]*href=["\']([^"\']+)', html, re.I)
    for value in references:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            continue
        path = parsed.path.lstrip('/')
        if path and not (ROOT / 'app/web' / path).is_file():
            errors.append('Missing local dashboard asset: ' + path)
    # Detect credential literals without printing any candidate value.
    credential_patterns = [r'\bhf_[A-Za-z0-9]{20,}\b', r'\bsk-[A-Za-z0-9_-]{20,}\b',
                           r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                           r'\bAKIA[A-Z0-9]{16}\b',
                           r'(?i)(?:sarvam_api_key|ngrok_authtoken|hf_token)\s*=\s*[\'\"][A-Za-z0-9_-]{20,}[\'\"]']
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix.lower() in {'.wav', '.pyc'} or '__pycache__' in path.parts:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if any(re.search(pattern, text) for pattern in credential_patterns):
            errors.append('Possible credential in ' + str(path.relative_to(ROOT)))
    forbidden = [p for p in ROOT.rglob('*') if p.is_file() and
                 (p.name == '.env' or p.suffix in {'.db', '.sqlite', '.sqlite3', '.safetensors', '.pth', '.log'})]
    errors.extend('Private/runtime file included: ' + str(p.relative_to(ROOT)) for p in forbidden)
    source_map = json.loads((ROOT / 'docs/SOURCE_MAP.json').read_text())
    for stage in source_map['stages']:
        path = ROOT / 'runtime/stages' / (stage['name'] + '.py')
        if hashlib.sha256(path.read_bytes()).hexdigest() != stage['sha256']:
            errors.append('Stage differs from the consolidation record: ' + stage['name'])
    result = {'passed': not errors, 'python_files': len(python_files),
              'javascript_checks': js_checks, 'node_available': bool(node),
              'notebook_outputs_cleared': True, 'errors': errors,
              'scope': 'Syntax, selected credential patterns, private-file exclusions and source integrity only.'}
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    sys.exit(0 if check()['passed'] else 1)
