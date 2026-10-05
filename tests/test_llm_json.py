"""大模型返回的 JSON 常带代码块标记或多余文字，解析要能容错。"""
import pytest

from ai.llm import _parse_json


@pytest.mark.parametrize("text", [
    '{"sql": "SELECT 1"}',
    '```json\n{"sql": "SELECT 1"}\n```',
    '好的，结果如下：{"sql": "SELECT 1"} 希望有帮助',
])
def test_parse_json_tolerates_wrappers(text):
    assert _parse_json(text)["sql"] == "SELECT 1"
