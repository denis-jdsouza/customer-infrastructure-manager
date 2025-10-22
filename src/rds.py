"""
This module defines the RDSManager class to manage AWS RDS instances.
It includes functionality to:
- Fetch the current state of an RDS instance.
- Wait for an RDS instance to reach a stable state.
- Start or stop an RDS instance.
"""

import socket
import time
import boto3


class RDSManager:
    """
    A class to fetch details and start/stop an AWS RDS instance.
    """
    # Default maximum retries for polling when an instance is not in a desired state
    MAX_RETRIES_DEFAULT = 120
    # Interval in seconds between status checks during polling
    CHECK_INTERVAL_SECONDS = 60

    def __init__(self, region_name):
        """
        Initializes the RDSManager with RDS client.
        """
        self.client = boto3.client("rds", region_name=region_name)

    @staticmethod
    def build_response(success: bool, message: str, **kwargs) -> dict:
        """
        Utility method to return standardized responses.
        """
        base_response = {
            "success": success,
            "message": message,
            "module": "RDSManager"
        }
        base_response.update(kwargs)
        return base_response

    def _get_rds_instance_status(self, rds_identifier: str) -> str:
        """
        Helper method to get the current status of an RDS instance.
        """
        try:
            response = self.client.describe_db_instances(
                DBInstanceIdentifier=rds_identifier)
            db_instances = response.get("DBInstances", [])
            if not db_instances:
                # Raise an explicit 'not found' exception if the instance is not in the response
                return self.build_response(
                    False,
                    f"RDS instance '{rds_identifier}' not found.",
                    rds_identifier=rds_identifier,
                    rds_exists=False
                )
            return db_instances[0].get("DBInstanceStatus", "unknown")
        except self.client.exceptions.DBInstanceNotFoundFault:
            return self.build_response(
                False,
                f"RDS instance '{rds_identifier}' not found.",
                rds_identifier=rds_identifier,
                rds_exists=False
            )
        except Exception as e:
            return self.build_response(
                False,
                f"Failed to get RDS instance status for '{rds_identifier}': {str(e)}",
                rds_identifier=rds_identifier
            )

    def wait_for_rds_state(self, rds_identifier: str, target_states: list) -> dict:
        """
        Polls the RDS instance status until it reaches one of the specified 'target_states'
        or the maximum number of retries is reached.
        """
        retries = 0
        current_status = "unknown"  # Initialize with a default status
        max_retries = self.MAX_RETRIES_DEFAULT
        check_interval = self.CHECK_INTERVAL_SECONDS

        while retries < max_retries:
            status_result = self._get_rds_instance_status(
                rds_identifier)
            if not isinstance(status_result, str):
                return status_result

            current_status = status_result
            if current_status in target_states:
                print(f"RDS instance '{rds_identifier}' reached target state '{current_status}'.\n")
                return self.build_response(
                    True,
                    f"RDS instance '{rds_identifier}' reached target state '{current_status}'.",
                    rds_state=current_status
                )

            print(
                f"RDS '{rds_identifier}' is in state '{current_status}'. "
                f"Waiting for {target_states}... (Retry {retries + 1}/{max_retries})"
            )
            time.sleep(check_interval)
            retries += 1

        return self.build_response(
            False,
            (
                f"Max retries ({max_retries}) reached. "
                f"RDS instance '{rds_identifier}' did not reach one of the target states: "
                f"{', '.join(target_states)}. Last known state: '{current_status}'."
            ),
            rds_state=current_status
        )

    def get_rds_status(self, rds_identifier: str) -> dict:
        """
        Retrieves the current status of RDS instance.
        """
        try:
            # Get initial status of the RDS instance
            status_result = self._get_rds_instance_status(
                rds_identifier)
            if not isinstance(status_result, str):
                return status_result

            # If the instance is not in 'stopped' or 'available' state start polling
            if status_result not in ['stopped', 'available']:
                print(
                    f"RDS instance '{rds_identifier}' is in state '{status_result}'. "
                    f"Polling for state to reach 'stopped' or 'available'..."
                )
                poll_result = self.wait_for_rds_state(
                    rds_identifier,
                    ['stopped', 'available']
                )
                return poll_result

            return self.build_response(
                True,
                f"RDS instance '{rds_identifier}' is in state '{status_result}'.",
                rds_identifier=rds_identifier,
                rds_exists=True,
                rds_state=status_result
            )

        except Exception as e:
            return self.build_response(
                False,
                f"Unexpected error: {str(e)}",
                rds_identifier=rds_identifier
            )

    def update_rds_status(self, rds_identifier: str, action: str) -> dict:
        """
        Updates the status of an RDS instance, 'start' or 'stop' it based on the action.
        """
        try:
            # Step 1: Check if the RDS instance exists and get its initial status
            initial_check = self.get_rds_status(rds_identifier)
            if not initial_check["success"]:
                return initial_check

            rds_identifier = initial_check.get("rds_identifier")
            current_state = initial_check.get("rds_state")

            # Step 2: If the current state is not 'stopped' or 'available', wait for it
            if current_state not in ['stopped', 'available']:
                print(
                    f"Waiting for RDS instance '{rds_identifier}' to reach stable state...")
                stable_result = self.wait_for_rds_state(
                    rds_identifier, ['stopped', 'available'])
                if not stable_result["success"]:
                    return stable_result
                current_state = stable_result["rds_state"]

            # Step 3: Perform 'up' or 'down' action
            if action.lower() == 'up':
                if current_state == 'available':
                    return self.build_response(
                        True,
                        f"RDS instance '{rds_identifier}' is already in available state."
                    )
                if current_state == 'stopped':
                    print(f"Starting RDS instance '{rds_identifier}'...")
                    self.client.start_db_instance(
                        DBInstanceIdentifier=rds_identifier)
                    wait_result = self.wait_for_rds_state(
                        rds_identifier, ['available'])
                    return wait_result

                return self.build_response(
                    False,
                    f"Cannot start RDS instance in current state '{current_state}'."
                )

            if action.lower() == 'down':
                if current_state == 'stopped':
                    return self.build_response(
                        True,
                        f"RDS instance '{rds_identifier}' is already stopped."
                    )
                if current_state == 'available':
                    print(f"Stopping RDS instance '{rds_identifier}'...")
                    self.client.stop_db_instance(
                        DBInstanceIdentifier=rds_identifier)
                    wait_result = self.wait_for_rds_state(
                        rds_identifier, ['stopped'])
                    return wait_result

                return self.build_response(
                    False,
                    f"Cannot stop RDS instance in current state '{current_state}'."
                )

            return self.build_response(
                False,
                f"Invalid action '{action}'. Must be 'up' or 'down'."
            )

        except self.client.exceptions.DBInstanceNotFoundFault:
            return self.build_response(
                False,
                f"RDS instance '{rds_identifier}' not found."
            )
        except Exception as e:
            return self.build_response(
                False,
                f"Unexpected error occurred: {str(e)}"
            )
