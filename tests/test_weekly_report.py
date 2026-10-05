"""自动周报：数字全部来自 SQL；数字核对能拦住编造的数字。"""
from ai import weekly_report


def test_collect_facts(con):
    f = weekly_report.collect_facts(con)
    assert f["period"]["end"] == "2017-12-03"
    assert f["summary"]["gmv"] > 0


def test_template_report_has_no_unverified_numbers(con):
    f = weekly_report.collect_facts(con)
    assert weekly_report.verify_numbers(weekly_report.template_report(f), f) == []


def test_verify_numbers_catches_made_up_number(con):
    f = weekly_report.collect_facts(con)
    text = weekly_report.template_report(f) + "\n- 本周转化率大幅提升 87.3%，GMV 达到 123456.7 万元。"
    bad = weekly_report.verify_numbers(text, f)
    assert "87.3" in bad and "123456.7" in bad


def test_made_up_decimals_are_mostly_caught(con):
    """随机编 500 个一位小数的百分比，至少 80% 要被拦下。
    旧版只按整数比对（87.3 只要数据里有 87 就放过），这项只有约 47%。"""
    import random
    f = weekly_report.collect_facts(con)
    rng = random.Random(0)
    fakes = [round(rng.uniform(1, 100), 1) for _ in range(500)]
    caught = sum(bool(weekly_report.verify_numbers(f"增长 {x}%", f)) for x in fakes)
    assert caught / len(fakes) >= 0.8, f"{caught}/{len(fakes)}"


def test_generate_falls_back_to_template_without_llm(con):
    rep = weekly_report.generate(con, use_llm=True)     # 测试环境没有配置大模型
    assert rep["source"] == "template"
    assert rep["markdown"].startswith("# 电商经营周报")


def test_verify_numbers_accepts_half_up_rounding():
    """数据是 1.3555（即 135.55%），大模型四舍五入写成 135.6% 是对的，不能误报；写 136.6% 才是错的"""
    facts = {"change": 1.3555, "other": -0.3755}
    assert weekly_report.verify_numbers("增长 135.6%，下降 37.6%", facts) == []
    assert weekly_report.verify_numbers("增长 136.6%", facts) == ["136.6"]
