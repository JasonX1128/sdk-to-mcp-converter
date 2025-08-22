# core/clients.py

from kubernetes import client, config
from github import Github
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
import os
from typing import Dict, Any

def _instantiate_class(class_path_str: str, init_args: dict = None):
    """Helper to dynamically import and instantiate a class."""
    parts = class_path_str.split('.')
    module_path = ".".join(parts[:-1])
    class_name = parts[-1]
    module = __import__(module_path, fromlist=[class_name])
    ApiClientClass = getattr(module, class_name)
    return ApiClientClass(**init_args) if init_args else ApiClientClass()

def init_kubernetes_clients(classes_to_expose: list, **kwargs) -> Dict[str, Any]:
    """Initializes Kubernetes API clients by loading kubeconfig."""
    print("Initializing Kubernetes clients...")
    config.load_kube_config()
    clients = {path: _instantiate_class(path) for path in classes_to_expose}
    print(f"Initialized {len(clients)} Kubernetes clients.")
    return clients

def init_github_client(classes_to_expose: list, auth_env_var: str, **kwargs) -> Dict[str, Any]:
    """Initializes the PyGithub client using a token from an env var."""
    print("Initializing GitHub client...")
    token = os.getenv(auth_env_var)
    if not token:
        print(f"Warning: GitHub token env var '{auth_env_var}' not set. Skipping.")
        return {}
    
    init_args = {'login_or_token': token}
    clients = {path: _instantiate_class(path, init_args) for path in classes_to_expose}
    print(f"Initialized {len(clients)} GitHub clients.")
    return clients

def init_azure_resource_client(classes_to_expose: list, auth_env_var: str, **kwargs) -> Dict[str, Any]:
    """Initializes an Azure client using DefaultAzureCredential."""
    print("Initializing Azure Resource Management client...")
    subscription_id = os.getenv(auth_env_var)
    if not subscription_id:
        print(f"Warning: Azure Subscription ID env var '{auth_env_var}' not set. Skipping.")
        return {}
        
    # DefaultAzureCredential will automatically use your logged-in Azure CLI credentials
    credential = DefaultAzureCredential()
    
    clients = {}
    for path in classes_to_expose:
        init_args = {'credential': credential, 'subscription_id': subscription_id}
        clients[path] = _instantiate_class(path, init_args)
        
    print(f"Initialized {len(clients)} Azure clients.")
    return clients