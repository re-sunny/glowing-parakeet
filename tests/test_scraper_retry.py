import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('scraper_krx', ROOT / 'scraper_krx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_should_retry_when_access_denied_detected(monkeypatch, tmp_path):
    calls = []

    class FakeDriver:
        def __init__(self):
            self.title = 'Access Denied'
            self.current_url = 'https://kind.krx.co.kr/disclosure/todaydisclosure.do?method=searchTodayDisclosureMain&marketType=0'
            self.page_source = '<html><body>Access Denied</body></html>'
            self.quit_called = False

        def get(self, url):
            calls.append(('get', url))

        def execute_cdp_cmd(self, *args, **kwargs):
            pass

        def execute_script(self, *args, **kwargs):
            pass

        def quit(self):
            self.quit_called = True

    def fake_create_driver(*args, **kwargs):
        return FakeDriver()

    monkeypatch.setattr(module, 'create_chrome_driver', fake_create_driver)

    def fake_sleep(seconds):
        calls.append(('sleep', seconds))

    monkeypatch.setattr(module.time, 'sleep', fake_sleep)

    class FakeWait:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def until(self, condition):
            raise Exception('not found')

    monkeypatch.setattr(module, 'WebDriverWait', FakeWait)

    original = tmp_path / '오늘의공시.xls'
    original.write_bytes(b'original data')
    result = module.download_today_disclosures(download_dir=str(tmp_path), max_retries=2, retry_delay=0)

    assert result is None
    assert original.read_bytes() == b'original data'
    assert calls.count(('get', 'https://kind.krx.co.kr/disclosure/todaydisclosure.do?method=searchTodayDisclosureMain&marketType=0')) >= 2


def test_success_uses_new_download_not_an_existing_excel(monkeypatch, tmp_path):
    unrelated = tmp_path / "other.xls"
    unrelated.write_bytes(b"unrelated")
    original = tmp_path / "오늘의공시.xls"
    original.write_bytes(b"previous snapshot")
    attempts = []

    class FakeDriver:
        def __init__(self, download_dir):
            self.download_dir = Path(download_dir)
            attempts.append(self)

        def get(self, url):
            pass

        def execute_script(self, script, *args):
            if 'click' in script:
                (self.download_dir / "오늘의공시.xls").write_bytes(f"snapshot {len(attempts)}".encode())

        def quit(self):
            pass

    class FakeWait:
        def __init__(self, *args):
            pass

        def until(self, condition):
            return object()

    monkeypatch.setattr(module, 'create_chrome_driver', FakeDriver)
    monkeypatch.setattr(module, 'WebDriverWait', FakeWait)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    for number in (1, 2):
        result = module.download_today_disclosures(str(tmp_path))
        assert Path(result) == original
        assert original.read_bytes() == f"snapshot {number}".encode()
    assert unrelated.read_bytes() == b"unrelated"
    assert attempts[0].download_dir != attempts[1].download_dir
    assert not list(tmp_path.glob('kind-*'))
