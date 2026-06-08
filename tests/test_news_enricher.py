# -*- coding: utf-8 -*-

import unittest

from filters.news_enricher import enrich_news_item


class NewsEnricherTest(unittest.TestCase):
    def test_cls_z_time_is_utc_to_beijing(self):
        item = enrich_news_item(
            {"title": "测试", "publish_time": "2026-06-04T00:41:40Z"},
            "cls",
        )
        self.assertEqual(item["publish_time_bj_display"], "2026-06-04 08:41:40")
        self.assertEqual(item["time_parse_note"], "cls_z_as_utc")

    def test_eastmoney_z_time_is_beijing_local(self):
        item = enrich_news_item(
            {"title": "测试", "publish_time": "2026-06-04T08:39:00Z"},
            "eastmoney_global",
        )
        self.assertEqual(item["publish_time_bj_display"], "2026-06-04 08:39:00")
        self.assertEqual(item["time_parse_note"], "eastmoney_global_z_as_beijing_local")

    def test_cninfo_midnight_z_time_is_utc_to_beijing(self):
        item = enrich_news_item(
            {"title": "公告", "publish_time": "2026-06-03T16:00:00Z"},
            "cninfo",
        )
        self.assertEqual(item["publish_time_bj_display"], "2026-06-04 00:00:00")

    def test_risk_announcement_is_marked(self):
        item = enrich_news_item(
            {
                "title": "关于股东拟减持股份暨股票交易异常波动风险提示公告",
                "publish_time": "2026-06-04T09:00:00Z",
            },
            "cninfo",
        )
        self.assertTrue(item["is_risk_alert"])
        self.assertEqual(item["risk_level"], "high")
        self.assertIn("share_reduction", item["risk_flags"])
        self.assertIn("abnormal_volatility", item["risk_flags"])
        self.assertGreaterEqual(item["news_score"], 75)

    def test_policy_news_gets_high_score(self):
        item = enrich_news_item(
            {
                "title": "国家发展改革委发布支持电力迎峰度夏政策通知",
                "content": "推动能源保供和电力投资。",
                "publish_time": "2026-06-04T09:00:00Z",
            },
            "ndrc",
        )
        self.assertEqual(item["news_tier"], "policy")
        self.assertTrue(item["is_high_impact"])
        self.assertGreaterEqual(item["news_score"], 70)


if __name__ == "__main__":
    unittest.main()
