# core/clients.py

from kubernetes import client, config
from typing import Dict, Any

def init_kubernetes_clients(classes_to_expose: list) -> Dict[str, Any]:
    """
    Initializes Kubernetes API clients.
    
    This function loads the kubeconfig file from the default location and
    instantiates the client classes specified in the config.
    """
    print("Initializing Kubernetes clients...")
    
    # Load Kubernetes configuration from default location (~/.kube/config)
    config.load_kube_config()
    
    initialized_clients = {}
    
    # We will dynamically instantiate the classes listed in our config
    for class_path_str in classes_to_expose:
        # For "kubernetes.client.CoreV1Api", this gets the CoreV1Api class
        parts = class_path_str.split('.')
        module_path = ".".join(parts[:-1])
        class_name = parts[-1]
        
        module = __import__(module_path, fromlist=[class_name])
        ApiClientClass = getattr(module, class_name)
        
        # Create an instance of the API client class
        instance = ApiClientClass()
        initialized_clients[class_path_str] = instance
        
    print(f"Initialized {len(initialized_clients)} Kubernetes clients.")
    return initialized_clients