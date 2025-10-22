"""
This module defines the InfraOrchestrator class
It manages and coordinates the state of cloud infrastructure components,
including AWS RDS, K8s deployments, application health checks, and S3-based state persistence.
"""

import time
from apphealth import AppHealthChecker
from rds import RDSManager
from k8s import K8sManager
from s3 import S3StateFileManager


class InfraOrchestrator:
    """
    A class to coordinate with infrastructure components to orchestrate the desired system state.

    Components:
    - AWS RDS
    - K8s deployments
    - Application health status
    - S3 state storage
    """

    def __init__(self, rds_region, s3_bucket_name, s3_region):
        """
        Initializes the InfraOrchestrator with the specified RDS region.
        """
        self.apphealth = AppHealthChecker()
        self.rds = RDSManager(rds_region)
        self.k8s = K8sManager()
        self.s3 = S3StateFileManager(s3_bucket_name, s3_region)

    @staticmethod
    def remove_keys(data_dict: dict, keys=("success", "module")):
        """
        Removes specified keys from a dictionary.
        """
        for key in keys:
            data_dict.pop(key, None)

    def get_environment_state(self, rds_identifier, deployments):
        """
        Retrieves the current state of the environment from RDS and K8s, including app health.
        """
        state_data = {
            "k8s_deployments": {},
            "aws_rds": {}
        }

        rds_status = self.rds.get_rds_status(rds_identifier)
        if rds_status["success"]:
            self.remove_keys(rds_status)
            state_data["aws_rds"] = rds_status
        else:
            return rds_status

        for name, namespace, health_url in deployments:
            deployment_status = self.k8s.get_deployment_status(name, namespace)
            health_status = self.apphealth.check_app_health(health_url)

            if deployment_status["success"] and health_status["success"]:
                self.remove_keys(deployment_status)
                self.remove_keys(health_status)
                state_data["k8s_deployments"].update(deployment_status)
                state_data["k8s_deployments"][name]["app_status"] = health_status["app_status"]
                state_data["k8s_deployments"][name]["app_url"] = health_status["app_url"]
            else:
                return deployment_status if not deployment_status["success"] else health_status

        return state_data

    def record_state_s3(self, s3_path, file_name, data_to_save):
        """
        Saves a JSON object as state into a S3 bucket.
        """
        return self.s3.record_state(s3_path, file_name, data_to_save)

    def get_previous_state_s3(self, s3_path, file_name):
        """
        Loads a previously stored state from S3.
        """
        return self.s3.load_state(s3_path, file_name)

    def update_environment_state(self, action, rds_region, rds_identifier, k8s_deployment_state):
        """
        Updates the state of infrastructure (RDS, K8s) based on the specified action.
        """
        sleep_sec = 60
        app_sleep_sec = 120
        def update_rds(rds_region):
            self.rds = RDSManager(rds_region)
            return self.rds.update_rds_status(rds_identifier, action)

        def update_k8s():
            for name, info in k8s_deployment_state.items():
                if info["deployment_exists"]:
                    desired_replicas = 0 if action == "down" else info["deployment_replicas"]
                    result = self.k8s.update_deployment_replicas(
                        name, info["deployment_namespace"], desired_replicas)
                    if not result["success"]:
                        return result
            print("All K8s deployments updated successfully..\n")
            return {"success": True, "message": "All K8s deployments updated successfully"}

        if action == "up":
            rds_result = update_rds(rds_region)
            if not rds_result["success"]:
                return rds_result
            print(f"Waiting {sleep_sec} seconds for RDS to be accessible..\n")
            time.sleep(sleep_sec)
            print("Updating K8s Deployments replica count to previous state..\n")
            k8s_result = update_k8s()
            if not k8s_result["success"]:
                return k8s_result
            print(f"Waiting {app_sleep_sec} seconds for application endpoints to be accessible..\n")
            time.sleep(app_sleep_sec)

        elif action == "down":
            print("Updating K8s Deployment replica count to 0..\n")
            k8s_result = update_k8s()
            if not k8s_result["success"]:
                return k8s_result
            print(f"Waiting {sleep_sec} seconds for pods to be terminated..\n")
            time.sleep(sleep_sec)
            rds_result = update_rds(rds_region)
            if not rds_result["success"]:
                return rds_result

        else:
            return {"success": False, "message": "Action not supported", "action": action}

        return {
            "success": True,
            "message": "RDS and K8s deployments updated successfully..",
            "action": action
        }
