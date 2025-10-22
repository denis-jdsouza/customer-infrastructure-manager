"""
Entry point to initiate InfraOrchestrator module.
Handles 'up', 'down' and 'get_env_state' actions on customer environment.

Customize the 'USER CONFIGURATION SECTION' below to match your infrastructure.
"""

import json
import sys
import os
from datetime import datetime, timezone
from kubeconfig_helper import update_kubeconfig
from orchestrator import InfraOrchestrator

# Automation expect the below environment variables to be set.
envs = {
    "eks_cluster": os.getenv("EKS_CLUSTER"),
    "aws_region": os.getenv("AWS_REGION"),
    "jbuild": os.getenv("BUILD_NUMBER"),
    "juser": os.getenv("BUILD_USER"),
    "customer": os.getenv("CUSTOMER"),
    "env": os.getenv("ENVIRONMENT"),
    "action": os.getenv("ACTION"),
    "s3_bucket_name": os.getenv("S3_BUCKET_NAME"),
    "s3_region": os.getenv("S3_REGION")
}

# ==============================================================================
# 🎯 USER CONFIGURATION SECTION 🎯
# ==============================================================================

# These variables define the structure of your environment and S3 storage.
# Update the template strings below to reflect your K8s, RDS and S3 setup.

# --- Infrastructure Identifiers ---

# Namespace for your Kubernetes deployments (e.g., 'customer-staging')
NAMESPACE_FORMAT = f"{envs['customer']}-{envs['env']}"
# RDS identifier for your database instance (e.g., 'customer-staging-rds')
RDS_IDENTIFIER_FORMAT = f"{envs['customer']}-{envs['env']}-rds"

# --- K8s Deployments List ---

# Add or remove entries here to match the number of deployments you want to manage.
# Format: [("deployment-name", "namespace", "app-health-check-url")]
DEPLOYMENTS = [
    ("frontend-deployment", NAMESPACE_FORMAT, f"https://frontend-{envs['env']}-{envs['customer']}.example.com/healthz"),
    ("backend-deployment", NAMESPACE_FORMAT, f"https://backend-{envs['env']}-{envs['customer']}.example.com/healthz")
]

# --- S3 State Paths ---

# File name for the environment state before performaing action (pre-state)
prestate_file = "pre-state.json"
# File name for the environment state after performaing action (post-state)
poststate_file = "post-state.json"
# File name for recording the details of the executed actions
actions_file = "actions.json"

# S3 paths used for storing environment state (pre-state, post-state) and actions history.
S3_PATHS_FORMAT = [
    # Path for historical record (specific to a Jenkins build number)
    f"/{envs['eks_cluster']}/{envs['customer']}/{envs['env']}/history/{envs['jbuild']}",
    # Path for general historical records
    f"/{envs['eks_cluster']}/{envs['customer']}/{envs['env']}/history/",
    # Path for the latest action (used for 'validate_actions')
    f"/{envs['eks_cluster']}/{envs['customer']}/{envs['env']}"
]

# --- Actions Data ---

# Data structure recorded in 'actions_file'.
# Tracks who performed the action, when and what the intended state was.
timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
actions = {
    "timestamp": timestamp,                   # UTC time when the action was initiated
    "jenkins_build": envs['jbuild'],          # Build number/ID from the CI system
    "jenkins_user": envs['juser'].strip('"'), # User who triggered the build
    "customer": envs['customer'],             # Customer name
    "environment": envs['env'],               # Customer Environment (e.g., staging, prod)
    "desired_state": envs['action']           # The action performed ('up', 'down', or 'get_env_state')
}

# ==============================================================================
# 🛠️ CORE ORCHESTRATION LOGIC 🛠️
# ==============================================================================

def print_result(label, result):
    """
    Prints a successful result in 'green' with a given label.
    """
    print(f"\033[1;32m[=== {label} ===]\033[0m")
    print(json.dumps(result, indent=2) + "\n")


def handle_error(label, result):
    """
    Prints an error result in 'red' and exits the script.
    """
    print(f"\033[1;31m[=== ERROR in {label} ===]\033[0m")
    print(json.dumps(result, indent=2) + "\n")
    sys.exit(1)


def get_env_state(orchestrator, rds_identifier, deployments, timestamp, jenkins_build):
    """
    Fetches the current environment state from orchestrator and prints it.
    """
    result = orchestrator.get_environment_state(rds_identifier, deployments)
    if "success" not in result:
        result["timestamp"] = timestamp
        result["jenkins_build"] = jenkins_build
        print_result("get_environment_state: Current", result)
    else:
        handle_error("get_environment_state: Current", result)
    return result


def record_env_state(orchestrator, s3_path, file_name, env_state):
    """
    Records the environment state into a S3 path.
    """
    result = orchestrator.record_state_s3(s3_path, file_name, env_state)
    if result.get("success"):
        print_result(f"record_state_s3: {file_name}", result)
    else:
        handle_error(f"record_state_s3: {file_name}", result)
    return result


def get_previous_state(orchestrator, s3_path, file_name):
    """
    Retrieves the previously saved environment state from S3.
    """
    result = orchestrator.get_previous_state_s3(s3_path, file_name)
    if result.get("success"):
        print_result(f"get_previous_state_s3: {file_name}", result)
    else:
        handle_error(f"get_previous_state_s3: {file_name}", result)
    return result


def update_env_state(orchestrator, action, rds_region, rds_identifier, k8s_state):
    """
    Updates the environment to match the desired state based on the specified action.
    """
    result = orchestrator.update_environment_state(
        action, rds_region, rds_identifier, k8s_state)
    if result.get("success"):
        print_result("update_environment_state", result)
    else:
        handle_error("update_environment_state", result)
    return result


def record_actions(orchestrator, s3_paths, file_name, actions):
    """
    Records the actions performed to one or more S3 paths.
    """
    for path in s3_paths:
        result = orchestrator.record_state_s3(path, file_name, actions)
        if result.get("success"):
            print_result(f"record_actions_s3: {file_name}", result)
        else:
            handle_error(f"record_actions_s3: {file_name}", result)


def validate_actions(orchestrator, s3_path, file_name, action):
    """
    Loads and validates a previously recorded action state from S3.
    Prevents repeating the same 'up' or 'down' action consecutively.
    """
    result = orchestrator.get_previous_state_s3(s3_path, file_name)

    if result.get("success"):
        previous_state = result["data"].get("desired_state")
        if previous_state == action and action in ("up", "down"):
            print(
                f"\033[1;31m Action '{action}' already performed in previous run.\033[0m")
            print(
                "\033[1;31m Not allowed to repeat the same action in consecutive runs. Exiting...\033[0m")
            sys.exit(1)
        return result
    
    message = result.get("message", "")
    if message.startswith("404"):
        print(
            "\033[1;33m Previous state not found in S3. This is possibly the first run. \033[0m")
        if action == "up":
            print(
                f"\033[1;31m Action '{action}' not allowed in the first run (must start with 'down' or 'get_env_state'). Exiting... \033[0m")
            sys.exit(1)
        return {
            "success": False,
            "message": "Previous state not found in S3. This is possibly the first run."
        }
    
    # Unknown error or failure
    print(f"\033[1;31m {result} \033[0m")
    sys.exit(1)


def update_kubeconfig_file(cluster, aws_region):
    """
    Updates the local kubeconfig for the given EKS cluster
    """
    print(f"Attempting to update kubeconfig for cluster: {cluster} in region: {aws_region}")
    try:
        update_kubeconfig(cluster, aws_region)
        print("\033[1;32m Kubeconfig updated successfully. \033[0m")
    except Exception as e:
        print(f"\033[1;31m Error updating kubeconfig: {e} \033[0m")
        sys.exit(1)


def main():
    """
    Initializes orchestrator and executes the requested action ('up', 'down', 'get_env_state').
    """
    action = envs['action']
    rds_region = envs['aws_region']
    rds_identifier = RDS_IDENTIFIER_FORMAT
    deployments = DEPLOYMENTS
    s3_bucket_name = envs['s3_bucket_name']
    s3_region = envs['s3_region']
    s3_paths = S3_PATHS_FORMAT
    
    # 1. Prepare Kubeconfig file
    update_kubeconfig_file(envs['eks_cluster'], envs['aws_region'])
    orchestrator = InfraOrchestrator(rds_region, s3_bucket_name, s3_region)

    # 2. Execute Action Logic
    if action == "up":
        # Check previous action to prevent consecutive 'up'
        actions_state = validate_actions(orchestrator, s3_paths[2], actions_file, action)
        previous_jenkins_build = actions_state["data"]["jenkins_build"]

        # Get current state before 'up' action is performed
        pre_env_state = get_env_state(
            orchestrator, rds_identifier, deployments, timestamp, envs['jbuild'])
        
        # Retrieve the state from S3 to 'scale-up' resources (previous run's pre-state)
        pre_env_state_s3 = get_previous_state(
            orchestrator, s3_paths[1] + previous_jenkins_build, prestate_file)
        k8s_state = pre_env_state_s3["data"]["k8s_deployments"]

        # Apply the 'up' action (will scale-up K8s Deployment replicas to previous state & start RDS)
        update_env_state(orchestrator, action, rds_region, rds_identifier, k8s_state)
        
        # Get current state after 'up' action is performed
        post_env_state = get_env_state(
            orchestrator, rds_identifier, deployments, timestamp, envs['jbuild'])
        
        # Record states & action after 'up' operation is completed
        record_env_state(
            orchestrator, s3_paths[0], prestate_file, pre_env_state)
        record_env_state(
            orchestrator, s3_paths[0], poststate_file, post_env_state)
        record_actions(
            orchestrator, [s3_paths[0], s3_paths[2]], actions_file, actions)

    elif action == "down":
        # Check previous action to prevent consecutive 'down'
        validate_actions(orchestrator, s3_paths[2], actions_file, action)

        # Get current state before 'down' action is performed
        pre_env_state = get_env_state(
            orchestrator, rds_identifier, deployments, timestamp, envs['jbuild'])
        k8s_state = pre_env_state["k8s_deployments"]
        
        # Apply the 'down' action (will scale-down K8s Deployment replicas to 0 & shutdown RDS)
        update_env_state(orchestrator, action, rds_region, rds_identifier, k8s_state)
        
        # Get current state after 'down' action is performed
        post_env_state = get_env_state(
            orchestrator, rds_identifier, deployments, timestamp, envs['jbuild'])
        
        # Record states & action after 'down' operation is completed
        record_env_state(
            orchestrator, s3_paths[0], prestate_file, pre_env_state)
        record_env_state(
            orchestrator, s3_paths[0], poststate_file, post_env_state)
        record_actions(
            orchestrator, [s3_paths[0], s3_paths[2]], actions_file, actions)

    elif action == "get_env_state":
        # Check previous action (from S3) and display it
        actions_state = validate_actions(orchestrator, s3_paths[2], actions_file, action)
        if actions_state.get("success"):
            print_result(
                f"Previous Action: {actions_state['data']['desired_state']}", actions_state["data"])
        else:
            print_result(actions_state["message"], {})
        
        # Get and display current environment state
        get_env_state(orchestrator, rds_identifier,
                      deployments, timestamp, envs['jbuild'])

    else:
        handle_error("input_validation", {
                     "success": False, "message": f"Invalid action: {action}"})


if __name__ == "__main__":
    main()
