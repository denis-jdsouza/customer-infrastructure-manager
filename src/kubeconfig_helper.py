"""
Helper function to update local kubeconfig
for a specified AWS EKS cluster using AWS CLI.
"""

import subprocess
import sys


def update_kubeconfig(cluster: str, aws_region: str) -> None:
    """
    Updates the local kubeconfig for the given EKS cluster.
    """

    command = [
        "aws", "eks", "update-kubeconfig",
        "--region", aws_region,
        "--name", cluster
    ]

    try:
        subprocess.run(command, check=True, stdout=sys.stdout, stderr=sys.stderr)
        print(f"Kubeconfig updated for cluster: {cluster}\n")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed with exit code {e.returncode}: {e}") from e
    except FileNotFoundError as e:
        raise RuntimeError("AWS CLI not found. Make sure it is installed and in PATH") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error while updating kubeconfig: {e}") from e
