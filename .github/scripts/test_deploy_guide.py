import unittest

import deploy_guide as d


class Headers(unittest.TestCase):
    def test_parity_overrides(self):
        for name in ["a.kibana", "a.console", "a.sense", "a.woff2", "a.yaml", "a.map"]:
            self.assertEqual(d.headers(name)["ContentType"], "application/octet-stream", name)
        self.assertEqual(d.headers("a.woff")["ContentType"], "application/font-woff")
        self.assertEqual(d.headers("a.js")["ContentType"], "application/javascript; charset=utf-8")
        self.assertEqual(d.headers("a.xml")["ContentType"], "text/xml; charset=utf-8")

    def test_standard_types(self):
        self.assertEqual(d.headers("x/index.html")["ContentType"], "text/html")
        self.assertEqual(d.headers("a.css")["ContentType"], "text/css")
        self.assertEqual(d.headers("a.json")["ContentType"], "application/json")
        self.assertEqual(d.headers("a.svg")["ContentType"], "image/svg+xml")
        self.assertEqual(d.headers("a.png")["ContentType"], "image/png")

    def test_edge_ttl(self):
        self.assertEqual(d.headers("a.html")["CacheControl"], "public, max-age=300")


class Key(unittest.TestCase):
    def test_maps_tree_path_to_s3_key(self):
        self.assertEqual(d.key("html/en/a.html"), "guide/en/a.html")


class PlanDiff(unittest.TestCase):
    def test_statuses(self):
        up, de = d.plan_diff(["A", "html/a.html", "M", "html/b.html", "T", "html/c.html", "D", "html/d.html",
                              "M", 'html/en/kibana/8.18/"role-api.html'])
        self.assertEqual(up, ["html/a.html", "html/b.html", "html/c.html", 'html/en/kibana/8.18/"role-api.html'])
        self.assertEqual(de, ["html/d.html"])

    def test_rename_is_rejected(self):
        with self.assertRaises(ValueError):
            d.plan_diff(["R100", "html/a.html"])

    def test_odd_token_count_is_rejected(self):
        with self.assertRaises(ValueError):
            d.plan_diff(["M"])


class Extras(unittest.TestCase):
    def test_deletes_extras_but_keeps_404(self):
        de = d.extras(["html/a.html", "html/b/c.css"],
                      ["guide/a.html", "guide/old.html", "guide/404.html", "_meta/deployed-sha"])
        self.assertEqual(de, ["html/old.html"])


if __name__ == "__main__":
    unittest.main()
