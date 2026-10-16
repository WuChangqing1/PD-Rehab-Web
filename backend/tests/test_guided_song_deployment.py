from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
def test_guided_song_websocket_has_dedicated_upgrade_routes():
    for file,location in [('pd-rehab.conf','/api/live-emotion/stream'),('pd-rehab-locations.conf','/pd-rehab/api/live-emotion/stream')]:
        text=(ROOT/'deploy'/'nginx'/file).read_text(encoding='utf-8')
        match=re.search(r'location = '+re.escape(location)+r'\s*\{([^}]+)\}',text)
        assert match, f'Missing WebSocket route: {location}'
        block=match.group(1)
        assert 'proxy_http_version 1.1;' in block
        assert 'proxy_set_header Upgrade $http_upgrade;' in block
        assert 'proxy_set_header Connection "upgrade";' in block
        assert 'proxy_buffering off;' in block
        assert 'http://127.0.0.1:18086/api/live-emotion/stream;' in block
