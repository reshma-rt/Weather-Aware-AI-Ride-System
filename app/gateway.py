
import asyncio
import os
from pathlib import Path
import httpx
import uvicorn
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response, FileResponse

app = FastAPI()
WEB_HTTP = 'http://127.0.0.1:8080'
AI_HTTP = 'http://127.0.0.1:8000'
CALL_PAGE = Path(os.environ['MOVIO_SITE_DIR']) / 'integrations/ai_call_page.html'
HOP = {'host', 'connection', 'content-length', 'transfer-encoding', 'keep-alive',
       'proxy-authenticate', 'proxy-authorization', 'te', 'trailer', 'upgrade'}

@app.get('/gateway-health')
def gateway_health():
    return {'ok': True, 'service': 'movio-gateway'}

@app.get('/call-page')
def call_page():
    return FileResponse(CALL_PAGE, media_type='text/html', headers={'Cache-Control': 'no-store'})

@app.websocket('/browser-call')
async def voice_socket(ws: WebSocket):
    origin = ws.headers.get('origin', '').rstrip('/')
    if not origin or origin != 'https://' + ws.headers.get('host', ''):
        await ws.close(code=1008)
        return
    query = str(ws.url.query)
    target = 'ws://127.0.0.1:8000/browser-call' + ('?' + query if query else '')
    try:
        async with websockets.connect(target, origin=origin, max_size=10_000_000) as upstream:
            await ws.accept()
            async def client_to_ai():
                while True:
                    message = await ws.receive()
                    if message['type'] == 'websocket.disconnect':
                        return
                    if message.get('text') is not None:
                        await upstream.send(message['text'])
                    elif message.get('bytes') is not None:
                        await upstream.send(message['bytes'])
            async def ai_to_client():
                async for message in upstream:
                    if isinstance(message, bytes):
                        await ws.send_bytes(message)
                    else:
                        await ws.send_text(message)
            tasks = [asyncio.create_task(client_to_ai()), asyncio.create_task(ai_to_client())]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as error:
        print('WebSocket gateway error:', type(error).__name__, flush=True)
        try:
            await ws.close(code=1011)
        except Exception:
            pass

@app.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
async def proxy(request: Request, path: str):
    backend = AI_HTTP if path in {'health', 'weather-speech'} else WEB_HTTP
    url = backend + request.url.path
    if request.url.query:
        url += '?' + request.url.query
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    headers['accept-encoding'] = 'identity'
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        upstream = await client.request(request.method, url, headers=headers,
                                        content=await request.body(), follow_redirects=False)
    response = Response(content=upstream.content, status_code=upstream.status_code)
    excluded = HOP | {'content-encoding'}
    for key, value in upstream.headers.multi_items():
        if key.lower() not in excluded:
            response.headers.append(key, value)
    return response

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8090, log_level='warning')
