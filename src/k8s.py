"""
This module defines the K8sManager class, which provides methods to interact with
Kubernetes deployments, including fetching deployment status and scaling replicas.
"""

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


class K8sManager:
    """
    A class to fetch details and update the replica count of K8s deployments.
    """
    MODULE_NAME = "K8sManager"

    def __init__(self, kubeconfig_path: str = None):
        """
        Initializes the Kubernetes API clients using kubeconfig file.
        """
        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_kube_config()

        self.apps_v1 = client.AppsV1Api()

    @classmethod
    def build_response(cls, success: bool, message: str, **kwargs) -> dict:
        """
        Utility method to return standardized responses.
        """
        return {
            "success": success,
            "message": message,
            "module": cls.MODULE_NAME,
            **kwargs
        }

    @classmethod
    def _init_deployment_result(cls, deployment: str, namespace: str) -> dict:
        """
        Utility method to return standardized dataset for K8s deployment.
        """
        return {
            "success": True,
            "module": cls.MODULE_NAME,
            deployment: {
                "deployment_namespace": namespace,
                "deployment_exists": False,
                "deployment_available": None,
                "deployment_available_reason": None,
                "deployment_replicas": None
            }
        }

    def get_deployment_status(self, deployment: str, namespace: str) -> dict:
        """
        Get status of a deployment: availability, replicas, namesapce.
        """
        result = self._init_deployment_result(deployment, namespace)

        try:
            deploy = self.apps_v1.read_namespaced_deployment(
                name=deployment, namespace=namespace)
            replicas = deploy.spec.replicas or 0
            is_available = False
            available_reason = None

            if replicas > 0:
                for condition in deploy.status.conditions or []:
                    if condition.type == "Available":
                        is_available = condition.status == "True"
                        available_reason = condition.reason or None
                        break

            result[deployment].update({
                "deployment_exists": True,
                "deployment_available": is_available,
                "deployment_available_reason": available_reason,
                "deployment_replicas": replicas
            })

        except ApiException as e:
            if e.status == 404:
                result[deployment]["deployment_message"] = (
                    f"Deployment '{deployment}' not found in namespace '{namespace}'"
                )
            else:
                return self.build_response(
                    False,
                    f"API error while fetching deployment: {e.reason} (HTTP {e.status})"
                )
        except Exception as e:
            return self.build_response(
                False,
                f"Unexpected error while getting deployment status: {str(e)}"
            )

        return result

    def update_deployment_replicas(self, deployment: str, namespace: str, replica_count: int) -> dict:
        """
        Update the replica count for a deployment.
        """
        try:
            _ = self.apps_v1.read_namespaced_deployment(
                name=deployment, namespace=namespace)

            patch = {"spec": {"replicas": replica_count}}

            self.apps_v1.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=patch
            )

            return self.build_response(
                True,
                f"Replicas updated to {replica_count} for '{deployment}' in namespace '{namespace}'"
            )

        except ApiException as e:
            if e.status == 404:
                return self.build_response(
                    False,
                    f"Deployment '{deployment}' not found in namespace '{namespace}'"
                )
            return self.build_response(
                False,
                f"API error while updating deployment: {e.reason} (HTTP {e.status})"
            )

        except Exception as e:
            return self.build_response(
                False,
                f"Unexpected error while updating deployment: {str(e)}"
            )
