"""python -m unittest discover -s api/tests -t .   (server tests need ml/models/lgbm_v1.joblib)"""
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from api import jobposting as J

JP = {"@context": "https://schema.org", "@type": "JobPosting", "title": "Clerk",
      "description": "<p>Hello &amp; welcome</p><ul><li>Type fast</li></ul>",
      "hiringOrganization": {"@type": "Organization", "name": "Acme", "logo": "https://x/logo.png"},
      "employmentType": ["FULL_TIME"], "jobLocationType": "TELECOMMUTE",
      "baseSalary": {"value": {"minValue": "40000", "maxValue": 60000}},
      "educationRequirements": {"credentialCategory": "bachelor degree"},
      "jobLocation": [{"address": {"addressCountry": {"name": "United States"}, "addressRegion": "NY",
                                   "addressLocality": "New York"}}]}


class Mapping(unittest.TestCase):
    def test_full_jobposting(self):
        raw, unknown = J.to_raw(JP)
        self.assertEqual(raw["title"], "Clerk")
        self.assertIn("Hello & welcome", raw["description"])
        self.assertEqual(raw["location"], "US, NY, New York")
        self.assertEqual(raw["salary_range"], "40000-60000")
        self.assertEqual(raw["employment_type"], "Full-time")
        self.assertEqual(raw["required_education"], "Bachelor's Degree")
        self.assertEqual((raw["telecommuting"], raw["has_company_logo"]), (1, 1))
        self.assertIn("has_questions", unknown)
        self.assertNotIn("has_questions", raw)          # never guessed
        self.assertEqual(J.company_name(JP), "Acme")

    def test_free_text_location(self):
        self.assertEqual(J.free_location("San Francisco, CA"), "US, CA, San Francisco")
        self.assertEqual(J.free_location("London, United Kingdom"), "GB, , London")
        self.assertEqual(J.free_location("Remote"), ", , Remote")   # never guesses a country

    def test_minimal_and_nested(self):
        raw, unknown = J.to_raw({"@type": "JobPosting", "title": "X", "hiringOrganization": "Solo"})
        self.assertNotIn("has_company_logo", raw)       # no logo in the data = unknown, not "no logo"
        self.assertIn("has_company_logo", unknown)
        self.assertIn("company_profile", unknown)
        graph = {"@graph": [{"@type": "WebPage"}, {"@type": ["JobPosting"], "title": "Y"}]}
        self.assertEqual(J.find_jobposting(graph)["title"], "Y")
        self.assertIsNone(J.find_jobposting({"@type": "Organization"}))


def _have_model():
    from ml.run import bundle_path
    return bundle_path("lgbm").exists()


@unittest.skipUnless(_have_model(), "needs ml/models/lgbm_v1.joblib (python -m ml.run train --model lgbm)")
class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["RR_GRANITE"] = "off"     # template summaries: no model download in tests
        from api import main
        main.Handler.scorer = main.Scorer(granite=False)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), main.Handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.demo = main.DEMO

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, body=None):
        req = urllib.request.Request(self.url + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read()), r.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read()), e.headers

    def test_health(self):
        status, body, headers = self.call("/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")

    def test_scam_and_real_demo_listings(self):
        s, scam, _ = self.call("/score", {"jobposting": {"@type": "JobPosting", **self.demo["scam"]}})
        _, real, _ = self.call("/score", {"jobposting": {"@type": "JobPosting", **self.demo["real"]}})
        self.assertEqual(s, 200)
        self.assertGreater(scam["risk"], real["risk"])
        self.assertTrue(scam["flagged"])
        self.assertEqual(real["band"], "low")
        for r in (scam, real):
            self.assertTrue(0 <= r["risk"] <= 1)
            self.assertIn(r["band"], ("low", "medium", "high"))
            self.assertTrue(r["summary"].startswith("This posting"))
            self.assertEqual(r["summary_source"], "template")
            self.assertNotIn("has_questions", [x["field"] for x in r["reasons"]])
        self.assertIn("company_profile", scam["left_out"])   # not on the page: left out, not "missing"
        self.assertIn("has_company_logo", scam["left_out"])  # can't see a logo: left out, not "no logo"
        self.assertIn("has_questions", real["left_out"])

    def test_kaggle_style_posting(self):
        s, r, _ = self.call("/score", {"posting": {"title": "Accountant", "description": "Reconcile accounts.",
                                                   "has_company_logo": 1, "telecommuting": 0}})
        self.assertEqual(s, 200)
        self.assertEqual(r["unknown_inputs"], ["has_questions"])

    def test_bad_requests(self):
        self.assertEqual(self.call("/score", {})[0], 400)
        self.assertEqual(self.call("/score", {"posting": {"salary_range": "1-2"}})[0], 400)
        self.assertEqual(self.call("/nope", {})[0], 404)

    def test_summary_endpoint_falls_back_to_template(self):
        _, r, _ = self.call("/score", {"jobposting": {"@type": "JobPosting", **self.demo["scam"]}})
        s, g, _ = self.call("/summary", {"risk": r["risk"], "flagged": r["flagged"], "reasons": r["reasons"]})
        self.assertEqual(s, 200)
        self.assertEqual(g["summary_source"], "template")

    def test_demo_pages_carry_jsonld(self):
        with urllib.request.urlopen(self.url + "/demo/posting?case=scam", timeout=30) as r:
            page = r.read().decode()
        self.assertIn('"@type": "JobPosting"', page)


class GraniteGuard(unittest.TestCase):
    def test_wording_rules(self):
        from ml.granite import acceptable, template_summary
        self.assertTrue(acceptable("This posting shows signs often seen in scam listings, mainly the missing logo."))
        for bad in ("This posting is a scam.", "This posting has several red flags.", "The posting looks fine.",
                    "This posting is genuine and safe."):
            self.assertFalse(acceptable(bad), bad)
        t = template_summary(0.9, True, [{"text": "No company logo", "direction": "raises"}])
        self.assertTrue(acceptable(t.split(". ")[0] + "."))


if __name__ == "__main__":
    unittest.main()
