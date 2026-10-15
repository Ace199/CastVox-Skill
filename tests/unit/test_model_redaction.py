import json
import unittest

from studio_server import read_models
from tests.helpers import Fixture


class ModelRedaction(Fixture, unittest.TestCase):
    def test_credential_copied_into_model_metadata_is_rejected(self):
        for field in ("api_key", "password", "access_token"):
            path = self.dump("model-config.json", {field: "PRIVATE_RANDOM_VALUE", "models": [
                {"id": "model", "name": "label PRIVATE_RANDOM_VALUE"}], "default_model": "model"})
            output = read_models(path)
            self.assertNotIn("PRIVATE_RANDOM_VALUE", json.dumps(output))
            self.assertEqual(output["model_status"], "invalid_model_config")
