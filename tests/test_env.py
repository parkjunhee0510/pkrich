from __future__ import annotations

import os
import unittest

from src.utils.env import normalize_env_value, sanitize_proxy_environment


class EnvTests(unittest.TestCase):
    def test_sanitize_proxy_environment_removes_broken_local_proxy(self) -> None:
        original = {name: os.environ.get(name) for name in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]}
        try:
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
            os.environ["HTTPS_PROXY"] = "http://localhost:9"
            os.environ["ALL_PROXY"] = "http://[::1]:9"

            sanitize_proxy_environment()

            self.assertIsNone(os.environ.get("HTTP_PROXY"))
            self.assertIsNone(os.environ.get("HTTPS_PROXY"))
            self.assertIsNone(os.environ.get("ALL_PROXY"))
        finally:
            for name, value in original.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_sanitize_proxy_environment_keeps_non_broken_proxy(self) -> None:
        original = os.environ.get("HTTP_PROXY")
        try:
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:8080"
            sanitize_proxy_environment()
            self.assertEqual(os.environ.get("HTTP_PROXY"), "http://127.0.0.1:8080")
        finally:
            if original is None:
                os.environ.pop("HTTP_PROXY", None)
            else:
                os.environ["HTTP_PROXY"] = original

    def test_normalize_env_value_removes_matching_quotes(self) -> None:
        self.assertEqual(
            normalize_env_value('"C:\\Users\\junhe\\OneDrive\\문서\\Obsidian Vault"'),
            "C:\\Users\\junhe\\OneDrive\\문서\\Obsidian Vault",
        )
        self.assertEqual(
            normalize_env_value("'quoted-value'"),
            "quoted-value",
        )
        self.assertEqual(normalize_env_value("plain-value"), "plain-value")


if __name__ == "__main__":
    unittest.main()
