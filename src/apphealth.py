"""
This module defines the AppHealthChecker class
It determines the health status (up/down) of an application based on it's health check URL.
"""

import requests


class AppHealthChecker:
    """
    class to Determine the health status (up/down) of an application based on it's health check URL.
    """
    DEFAULT_TIMEOUT_SECONDS = 10
    MODULE_NAME = "AppHealthChecker"

    @classmethod
    def build_response(cls, success: bool, message: str, app_url: str, app_status=None) -> dict:
        """
        Utility method to return standardized responses.
        """
        return {
            "success": success,
            "message": message,
            "app_status": app_status,
            "app_url": app_url,
            "module": cls.MODULE_NAME
        }

    def check_app_health(self, url: str) -> dict:
        """
        Checks the health of an application by making an HTTP GET request to the provided URL.
        """
        try:
            response = requests.get(url, timeout=self.DEFAULT_TIMEOUT_SECONDS)

            if response.status_code == 200:
                return self.build_response(
                    True,
                    f"App health check successful. Status code: {response.status_code}.",
                    url,
                    app_status="up"
                )
            return self.build_response(
                True,
                f"App health check received non-200 status code: {response.status_code}.",
                url,
                app_status="down"
            )

        except requests.exceptions.Timeout:
            return self.build_response(
                True,
                f"Health check request timed out after {self.DEFAULT_TIMEOUT_SECONDS} seconds.",
                url,
                app_status="down"
            )

        except requests.exceptions.MissingSchema:
            return self.build_response(
                False,
                f"Invalid URL schema. Provide full URL like 'http://example.com': {url}",
                url
            )

        except requests.exceptions.InvalidURL:
            return self.build_response(
                False,
                f"Invalid URL format: {url}",
                url
            )

        except requests.exceptions.ConnectionError as e:
            msg = str(e)
            # Attempt to catch specific DNS failure messages
            if "Name or service not known" in msg or "nodename nor servname provided" in msg:
                return self.build_response(
                    False,
                    f"DNS resolution failed for '{url}'. Domain may not exist or is unreachable.",
                    url
                )
            return self.build_response(
                False,
                f"Connection error during health check for '{url}': {msg}",
                url,
                app_status="down"
            )

        except requests.exceptions.RequestException as e:
            # Catch any other requests-related exceptions (e.g., TooManyRedirects, HTTPError)
            return self.build_response(
                False,
                f"An HTTP error occurred for '{url}': {str(e)}",
                url,
                app_status="down"
            )

        except Exception as e:
            return self.build_response(
                False,
                f"Unexpected error during health check: {str(e)}",
                url
            )
