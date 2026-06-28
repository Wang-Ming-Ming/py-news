from datetime import datetime, timedelta, timezone

from analysis.emerging_theme_radar import NewsItem, discover_themes, extract_terms


BEIJING = timezone(timedelta(hours=8))


def item(
    title: str,
    hours_before: int,
    source: str,
    code: str = "",
) -> NewsItem:
    cutoff = datetime(2026, 6, 18, 8, 30, tzinfo=BEIJING)
    return NewsItem(
        title=title,
        source=source,
        published_at=cutoff - timedelta(hours=hours_before),
        stock_code=code,
        stock_name="",
        url="",
    )


def test_extract_terms_normalizes_inp_aliases() -> None:
    assert "磷化铟" in extract_terms("Coherent加速InP扩产")
    assert "磷化铟" in extract_terms("磷化铟衬底成为1.6T光模块瓶颈")
    assert "1.6T" in extract_terms("磷化铟衬底成为1.6T光模块瓶颈")


def test_discovers_cross_source_emerging_theme_before_stock_ranking() -> None:
    cutoff = datetime(2026, 6, 18, 8, 30, tzinfo=BEIJING)
    rows = [
        item("瞄准AI数据中心需求 磷化铟衬底巨头计划扩产", 55, "eastmoney_global"),
        item("全球磷化铟短缺 出口许可影响光模块交付", 44, "reuters"),
        item("英伟达携手Coherent扩产6英寸InP晶圆", 24, "cls"),
        item("某公司收购磷化铟业务相关资产", 16, "cninfo", "002674"),
        item("去年磷化铟行业普通回顾", 24 * 10, "eastmoney_global"),
    ]

    themes = discover_themes(rows, cutoff, recent_hours=72, baseline_days=21)
    inp = next(row for row in themes if row["term"] == "磷化铟")

    assert inp["stage"] == "emerging"
    assert inp["recent_count"] == 4
    assert inp["source_count"] == 4
    assert inp["primary_count"] == 1
    assert inp["overseas_signal_count"] == 2
    assert inp["foreign_primary_count"] == 1
    assert inp["needs_external_verification"] is False
    assert inp["direct_stock_codes"] == ["002674"]


def test_future_news_is_excluded_from_historical_cutoff() -> None:
    cutoff = datetime(2026, 6, 18, 8, 30, tzinfo=BEIJING)
    rows = [
        item("磷化铟短缺影响AI光模块", 1, "eastmoney_global"),
        item("磷化铟扩产仍需出口许可", 2, "cls"),
        NewsItem(
            title="兴业科技拟收购磷化铟业务",
            source="cninfo",
            published_at=cutoff + timedelta(days=3),
            stock_code="002674",
            stock_name="兴业科技",
            url="",
        ),
    ]

    inp = next(
        row
        for row in discover_themes(rows, cutoff, recent_hours=72, baseline_days=21)
        if row["term"] == "磷化铟"
    )

    assert inp["recent_count"] == 2
    assert inp["direct_stock_codes"] == []


def test_duplicate_reposts_and_denials_do_not_create_a_theme() -> None:
    cutoff = datetime(2026, 6, 18, 8, 30, tzinfo=BEIJING)
    rows = [
        item("某公司：当前业务不涉及固态电池", 2, "cls"),
        item("某公司：当前业务不涉及固态电池", 2, "eastmoney_global"),
        item("另一公司澄清没有相关固态电池业务", 8, "cls"),
    ]

    themes = discover_themes(rows, cutoff, recent_hours=72, baseline_days=21)

    assert themes == []


def test_generic_daily_chatter_can_return_no_new_theme() -> None:
    cutoff = datetime(2026, 6, 18, 8, 30, tzinfo=BEIJING)
    rows = [
        item("半导体行业今日上涨", 4, "eastmoney_global"),
        item("AI市场继续受到关注", 8, "cls"),
        item("机器人公司召开股东会", 12, "cninfo"),
    ]

    themes = discover_themes(rows, cutoff, recent_hours=72, baseline_days=21)

    assert themes == []
