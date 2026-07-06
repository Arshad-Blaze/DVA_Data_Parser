import os
import subprocess
import time
import tempfile
import logging
from typing import Generator, Dict

import pytest
import requests
from playwright.sync_api import Page, BrowserContext
from _pytest.nodes import Item
from _pytest.runner import CallInfo

from tests.e2e.sample_data import (
    create_flow_test_data,
    create_multiline_flow_test_data,
    create_hdr_trailer_test_data,
    create_config_test_data,
)

logger = logging.getLogger(__name__)

PERF_METRICS: Dict[str, float] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        duration = call.duration
        item.user_properties.append(("duration_seconds", round(duration, 3)))
        test_name = item.nodeid.split("::")[-1]
        PERF_METRICS[test_name] = duration


def pytest_sessionfinish(session, exitstatus):
    if PERF_METRICS:
        print("\n" + "=" * 60)
        print("  PERFORMANCE METRICS (test durations)")
        print("=" * 60)
        for name, dur in sorted(PERF_METRICS.items(), key=lambda x: -x[1]):
            print(f"  {name:50s} {dur:7.3f}s")
        print("=" * 60)

STREAMLIT_PORT = 18501
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"


def _find_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def streamlit_server() -> Generator[str, None, None]:
    port = _find_free_port()
    url = f"http://localhost:{port}"

    subprocess.run(
        f"lsof -ti:{port} | xargs -r kill -9",
        shell=True, capture_output=True, timeout=5,
    )

    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    app_path = os.path.join(repo_root, "dav_tool", "ui", "app.py")

    venv_dir = os.path.join(repo_root, "venv", "bin")
    env = os.environ.copy()
    env["STREAMLIT_SERVER_PORT"] = str(port)
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["PYTHONPATH"] = f"{repo_root}:{env.get('PYTHONPATH', '')}"
    current_path = env.get("PATH", "")
    env["PATH"] = f"{venv_dir}:{current_path}" if venv_dir not in current_path else current_path

    process = subprocess.Popen(
        ["streamlit", "run", app_path,
         "--server.port", str(port),
         "--server.headless", "true",
         "--global.developmentMode", "false"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
        cwd=repo_root,
    )

    max_retries = 60
    for i in range(max_retries):
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                logger.info(f"Streamlit server ready at {url} (attempt {i+1})")
                break
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(1)
    else:
        _, stderr = process.communicate(timeout=5)
        process.terminate()
        process.wait(timeout=10)
        pytest.fail(
            f"Streamlit server did not start on port {port}. "
            f"Stderr: {stderr.decode()[:500]}"
        )

    yield url

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.fixture(scope="session")
def test_data() -> Generator[Dict[str, str], None, None]:
    with tempfile.TemporaryDirectory(prefix="dav_e2e_") as tmpdir:
        data = create_flow_test_data(tmpdir)
        yield data


@pytest.fixture(scope="session")
def multiline_test_data() -> Generator[Dict[str, str], None, None]:
    with tempfile.TemporaryDirectory(prefix="dav_ml_e2e_") as tmpdir:
        data = create_multiline_flow_test_data(tmpdir)
        yield data


@pytest.fixture(scope="session")
def trl_test_data() -> Generator[Dict[str, str], None, None]:
    with tempfile.TemporaryDirectory(prefix="dav_trl_e2e_") as tmpdir:
        data = create_hdr_trailer_test_data(tmpdir)
        yield data


@pytest.fixture(scope="session")
def config_test_data() -> Generator[Dict[str, str], None, None]:
    with tempfile.TemporaryDirectory(prefix="dav_cfg_e2e_") as tmpdir:
        data = create_config_test_data(tmpdir)
        yield data


@pytest.fixture
def onb_page(page: Page, streamlit_server: str) -> Generator[Page, None, None]:
    page.goto(streamlit_server)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Onboarding").click()
    page.wait_for_timeout(1500)
    yield page


@pytest.fixture
def ex_page(page: Page, streamlit_server: str) -> Generator[Page, None, None]:
    page.goto(streamlit_server)
    page.wait_for_load_state("networkidle")
    yield page


def fill_path(page: Page, selector: str, path: str):
    page.fill(selector, "")
    page.fill(selector, path)
    page.press(selector, "Tab")
    page.wait_for_timeout(500)
