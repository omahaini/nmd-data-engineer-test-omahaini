"""Local tests: run with  python -m unittest discover tests  (needs pandas)."""
import importlib
import os
import sys
import unittest
from unittest import mock

import pandas as pd

try:  # boto3 ships with Lambda but may not be installed locally; the tests never call AWS
    import boto3  # noqa: F401
except ImportError:
    sys.modules["boto3"] = mock.Mock()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import orders_analytics  # noqa: E402

SAMPLE = os.path.join(ROOT, "sample_orders.csv")


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.read_csv(SAMPLE)

    def test_most_profitable_region(self):
        result = orders_analytics.calculate_most_profitable_region(self.df)
        self.assertEqual(result.loc[0, "Region"], "East")
        self.assertAlmostEqual(result.loc[0, "Total Profit"], 2465.5)

    def test_ship_method_per_category(self):
        result = orders_analytics.find_most_common_ship_method(self.df)
        modes = dict(zip(result["Category"], result["Most Common Ship Mode"]))
        self.assertEqual(modes["Office Supplies"], "Standard Class")
        # Furniture ties (Same Day vs Standard Class) -> alphabetical
        self.assertEqual(modes["Furniture"], "Same Day")
        self.assertEqual(len(modes), 3)

    def test_order_counts(self):
        result = orders_analytics.find_number_of_order_per_category(self.df)
        self.assertEqual(result["Order Count"].sum(), len(self.df))

    def test_missing_column_raises(self):
        with self.assertRaises(ValueError):
            orders_analytics.run_all_reports(self.df.drop(columns=["Region"]))


class HandlerTests(unittest.TestCase):
    def test_output_key_includes_folder_and_partition(self):
        handler = importlib.import_module("lambda")
        key = handler.build_output_key("most_profitable_region", "a/b/orders.csv", "2026-10-13")
        self.assertEqual(key, "most_profitable_region/ingest_date=2026-10-13/a_b_orders.csv")

    def test_non_csv_object_is_skipped(self):
        handler = importlib.import_module("lambda")
        fake_s3 = mock.Mock()
        event = {"Records": [{"s3": {"bucket": {"name": "in"}, "object": {"key": "notes.txt"}}}]}
        with mock.patch.object(handler, "s3_client", fake_s3), \
             mock.patch.dict(os.environ, {"OUTPUT_BUCKET": "out"}):
            result = handler.lambda_handler(event, None)
        self.assertEqual(result["reports_written"], [])
        fake_s3.get_object.assert_not_called()

    def test_handler_writes_three_reports(self):
        handler = importlib.import_module("lambda")  # 'lambda' is a keyword, so no 'import lambda'
        with open(SAMPLE, "rb") as f:
            csv_bytes = f.read()
        fake_s3 = mock.Mock()
        fake_s3.get_object.return_value = {"Body": mock.Mock(read=lambda: csv_bytes)}
        event = {"Records": [{"s3": {"bucket": {"name": "in"}, "object": {"key": "my+orders.csv"}}}]}
        with mock.patch.object(handler, "s3_client", fake_s3), \
             mock.patch.dict(os.environ, {"OUTPUT_BUCKET": "out"}):
            result = handler.lambda_handler(event, None)
        fake_s3.get_object.assert_called_once_with(Bucket="in", Key="my orders.csv")
        self.assertEqual(len(result["reports_written"]), 3)
        self.assertEqual(fake_s3.put_object.call_count, 3)


if __name__ == "__main__":
    unittest.main()
