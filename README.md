# ⚙️ Customer Infrastructure Manager

An automation framework designed to orchestrate and manage customer-specific cloud environments across Kubernetes (EKS), RDS and S3.

It provides a standardized way to bring environments up or down, as well as capture and record their state for auditing, rollback and CI/CD integrations.

_This automation is typically run within a CI/CD pipeline (like Jenkins) to ensure controlled, traceable infrastructure changes._

## 🎯 Purpose:
The tool acts as an orchestrator that integrates:
* **Kubernetes (EKS):** Scale up/down deployments (e.g. frontend/backend services).
* **Amazon RDS:** Start or stop database instances tied to the customer environment.
* **Amazon S3:** Record and retrieve historical states and action metadata.

## 🧠 Use Cases
* Automatically **suspend non-production environments** during off-hours to save cost.
* **Restore** a customer’s environment to its previous state.
* **Validate** infrastructure status via Jenkins jobs or manual runs.

## ⚙️ How It Works
At its core, the automation performs actions based on an environment variable called ACTION, which can be one of:
* **up** – Brings up an environment by restoring deployments and database to their last known state.
* **down** – Brings down an environment by scaling deployments to 0 replicas and stopping the database.
* **get_env_state** – Fetches and displays the current environment state (deployments, RDS and application status).

## 💡 Key Features
* **Controlled Scaling (Down):** The `down` action scales K8s deployments to zero replicas and shuts down the associated RDS instance.
* **Stateful Recovery (Up):** The `up` action retrieves the last known replica count from S3 and scales K8s deployments back to that state while starting the RDS instance.
* **Reliable RDS Status:** The system automatically **polls the RDS instance** when it is in a transient state (e.g., 'starting', 'stopping') to ensure the orchestration waits for a stable state ('available' or 'stopped') before proceeding.
* **Idempotent Actions:** Prevents consecutive execution of the same action (e.g., prevents running `up` immediately after another `up`).
* **State Tracking:** Records granular pre and post action environment state (K8s deployment, RDS status) to S3.
* **Auditability:** Every action is logged in `actions.json` with a timestamp, CI build ID, user, and the desired state for full traceability.

***

## 📁 Project Structure

The project is divided into logical modules within the `src/` directory:

| File Name | Description |
| :--- | :--- |
| `main.py` | **Entry Point.** Parses environment variables and orchestrates the 'up', 'down', or 'get\_env\_state' action via the `InfraOrchestrator`. |
| `orchestrator.py` | **Core Logic.** Contains the `InfraOrchestrator` class, which coordinates actions across K8s, RDS, S3 and Apphealth modules. |
| `k8s.py` | **K8sManager.** Handles Kubernetes operations, including deployment status checks and scaling resources. |
| `rds.py` | **RDSManager.** Manages AWS RDS operations, such as checking the database status and performing start/stop actions. |
| `s3.py` | **S3StateFileManager.** Provides functionality to record and retrieve JSON-based state and action history from S3 bucket. |
| `apphealth.py` | **AppHealthChecker.** Checks the health status of an application based on it's health check URL after deployment changes. |
| `kubeconfig_helper.py` | A utility to update the local Kubeconfig file for connecting to the target EKS cluster. |

***

## ⚙️ Setup and Configuration

### Prerequisites

Before running the automation, ensure you have:
1.  **Python 3.x** installed.
2.  **AWS Credentials** configured locally or in your CI environment with below permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EKSClusterAccess",
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RDSManagement",
      "Effect": "Allow",
      "Action": [
        "rds:StartDBInstance",
        "rds:StopDBInstance",
        "rds:DescribeDBInstances"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3StateManagement",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::<s3-bucket-name>",
        "arn:aws:s3:::<s3-bucket-name>/*"
      ]
    }
  ]
}

```
3.  Installed dependencies: `pip install -r requirements.txt`

_Note:_
* Replace 's3-bucket-name' with the actual bucket name used in your environment (e.g. customer-infra-manager).
* You’ll need appropriate Kubernetes RBAC permissions within the cluster (to scale deployments, read namespaces, etc.).

### Environment Variables

The `main.py` script requires the following environment variables to be set before execution (e.g. in a CI stage or via the included test `.env` file):

| Variable | Description | Example |
| :--- | :--- | :--- |
| `EKS_CLUSTER` | The name of your target Kubernetes cluster. | `eks-dev-cluster` |
| `AWS_REGION` | The AWS region for your EKS cluster & RDS instance. | `us-east-1` |
| `CUSTOMER` | Identifier for the customer/account context. | `alpha` |
| `ENVIRONMENT` | Identifier for customer deployment environment. | `dev` |
| `ACTION` | The desired operation: `up`, `down`, or `get_env_state`. | `up` |
| `BUILD_NUMBER` | CI/CD build ID for tracking (increment this number for each run). | `10` |
| `BUILD_USER` | CI/CD user ID for tracking (optional, but recommended). | `jenkins-user` |
| `S3_BUCKET_NAME` | S3 bucket for storing customer environemnt state. | `customer-infra-manager` |
| `S3_REGION` | The AWS region for S3 bucket. | `us-east-1` |

***

## 📝 Customizing the automation

The core infrastructure identifiers are defined in the **`main.py`** file and must be updated to match your specific setup.

Look for the `🎯 USER CONFIGURATION SECTION 🎯` in **`main.py`** and modify the following variables:

### 1. Infrastructure Identifiers

| Variable | Default Format | Description |
| :--- | :--- | :--- |
| **`NAMESPACE_FORMAT`** | `customer-env` | The Kubernetes namespace the deployments are in. |
| **`RDS_IDENTIFIER_FORMAT`** | `customer-env-rds` | The identifier for your RDS database instance. |

### 2. K8s Deployments List

This is the list of K8s deployments the automation will manage.

```python
# Add or remove entries here to match the number of deployments you want to manage.
# Format: [("deployment-name", "namespace", "app-health-check-url")]
DEPLOYMENTS = [
    ("frontend-deployment", NAMESPACE_FORMAT, f".../healthz"),
    ("backend-deployment", NAMESPACE_FORMAT, f".../healthz")
]
```

### 3. S3 State Paths

These variables define the file names and the S3 paths used for storing environment state and action history.

```python
# S3 state file names
prestate_file = "pre-state.json"   # State before the action is performed
poststate_file = "post-state.json" # State after the action is performed
actions_file = "actions.json"      # Records metadata about the action

# S3 paths used for storing environment state (customizable path structure)
S3_PATHS_FORMAT = [
    # ... path structure using envs['eks_cluster'], envs['customer'], etc. ...
]
```

### 4. Actions Data
This dictionary defines the data recorded into the actions.json file.

```bash
actions = {
    "timestamp": timestamp,                   # UTC time when the action was initiated
    "jenkins_build": envs['jbuild'],          # Build number/ID from the CI system
    "jenkins_user": envs['juser'],            # User who triggered the build
    "customer": envs['customer'],             # Customer identifier
    "environment": envs['env'],               # Environment (e.g., staging, prod)
    "desired_state": envs['action']           # The action performed ('up', 'down', or 'get_env_state')
}
```

### ▶️ Usage
The project is executed via a single command after setting the required environment variables:
```bash
# 1. Bring the environment up (scale-up)
# Note: 'up' is disallowed in the first run or immediately after another 'up'.
export ACTION="up"
source .env && python3 src/main.py

# 2. Take the environment down (scale-down)
export ACTION="down"
source .env && python3 src/main.py

# 3. Check the current state (without taking action)
export ACTION="get_env_state"
source .env && python3 src/main.py
```

### 💻 Example Execution Output
The automation provides verbose, color-coded output detailing the state before and after an action, along with a log of S3 state recording.

This snippet shows the flow for the **'up'** action:

```bash
[=== get_environment_state: Current ===]
{
  "k8s_deployments": {
    "frontend-deployment": {
      "deployment_namespace": "alpha-dev",
      "deployment_exists": true,
      "deployment_available": false,
      "deployment_available_reason": null,
      "deployment_replicas": 0,
      "app_status": "down",
      "app_url": "https://frontend-dev-alpha.example.com/healthz"
    },
    "backend-deployment": {
      "deployment_namespace": "alpha-dev",
      "deployment_exists": true,
      "deployment_available": false,
      "deployment_available_reason": null,
      "deployment_replicas": 0,
      "app_status": "down",
      "app_url": "https://backend-dev-alpha.example.com/healthz"
    }
  },
  "aws_rds": {
    "message": "RDS instance 'alpha-dev-rds' is in state 'stopped'.",
    "rds_identifier": "alpha-dev-rds",
    "rds_exists": true,
    "rds_state": "stopped"
  },
  "timestamp": "2025-10-21T08:42:57Z",
  "jenkins_build": "11"
}

[=== get_previous_state_s3: pre-state.json ===]
{
  "success": true,
  "message": "S3 file 'eks-dev-cluster/alpha/dev/history/10/pre-state.json' loaded successfully",
  "module": "S3StateFileManager",
  "data": {
    "k8s_deployments": {
      "frontend-deployment": {
        "deployment_namespace": "alpha-dev",
        "deployment_exists": true,
        "deployment_available": true,
        "deployment_available_reason": "MinimumReplicasAvailable",
        "deployment_replicas": 1,
        "app_status": "up",
        "app_url": "https://frontend-dev-alpha.example.com/healthz"
      },
      "backend-deployment": {
        "deployment_namespace": "alpha-dev",
        "deployment_exists": true,
        "deployment_available": true,
        "deployment_available_reason": "MinimumReplicasAvailable",
        "deployment_replicas": 2,
        "app_status": "up",
        "app_url": "https://backend-dev-alpha.example.com/healthz"
      }
    },
    "aws_rds": {
      "message": "RDS instance 'alpha-dev-rds' is in state 'available'.",
      "rds_identifier": "alpha-dev-rds",
      "rds_exists": true,
      "rds_state": "available"
    },
    "timestamp": "2025-10-21T08:41:25Z",
    "jenkins_build": "10"
  }
}

Starting RDS instance 'alpha-dev-rds'...
RDS instance 'alpha-dev-rds' reached target state 'available'.

Waiting 60 seconds for RDS to be accessible..

Updating K8s Deployments replica count to previous state..

All K8s deployments updated successfully..

Waiting 120 seconds for application endpoints to be accessible..

[=== update_environment_state ===]
{
  "success": true,
  "message": "RDS and K8s deployments updated successfully..",
  "action": "up"
}

[=== get_environment_state: Current ===]
{
  "k8s_deployments": {
    "frontend-deployment": {
      "deployment_namespace": "alpha-dev",
      "deployment_exists": true,
      "deployment_available": true,
      "deployment_available_reason": "MinimumReplicasAvailable",
      "deployment_replicas": 1,
      "app_status": "up",
      "app_url": "https://frontend-dev-alpha.example.com/healthz"
    },
    "backend-deployment": {
      "deployment_namespace": "alpha-dev",
      "deployment_exists": true,
      "deployment_available": true,
      "deployment_available_reason": "MinimumReplicasAvailable",
      "deployment_replicas": 2,
      "app_status": "up",
      "app_url": "https://backend-dev-alpha.example.com/healthz"
    }
  },
  "aws_rds": {
    "message": "RDS instance 'alpha-dev-rds' is in state 'available'.",
    "rds_identifier": "alpha-dev-rds",
    "rds_exists": true,
    "rds_state": "available"
  },
  "timestamp": "2025-10-21T08:42:57Z",
  "jenkins_build": "11"
}

[=== record_state_s3: pre-state.json ===]
{
  "success": true,
  "message": "State successfully recorded to S3 file 'eks-dev-cluster/alpha/dev/history/11/pre-state.json'",
  "module": "S3StateFileManager"
}

[=== record_state_s3: post-state.json ===]
{
  "success": true,
  "message": "State successfully recorded to S3 file 'eks-dev-cluster/alpha/dev/history/11/post-state.json'",
  "module": "S3StateFileManager"
}

[=== record_actions_s3: actions.json ===]
{
  "success": true,
  "message": "State successfully recorded to S3 file 'eks-dev-cluster/alpha/dev/history/11/actions.json'",
  "module": "S3StateFileManager"
}

[=== record_actions_s3: actions.json ===]
{
  "success": true,
  "message": "State successfully recorded to S3 file 'eks-dev-cluster/alpha/dev/actions.json'",
  "module": "S3StateFileManager"
}
```
