import sys
from unittest.mock import MagicMock


streamlit_mock = MagicMock()
streamlit_mock.session_state = {}
streamlit_mock.secrets = {}
streamlit_mock.cache_data = lambda func=None, **kw: (func if func else (lambda f: f))
streamlit_mock.cache_resource = lambda func=None, **kw: (func if func else (lambda f: f))

sys.modules["streamlit"] = streamlit_mock
