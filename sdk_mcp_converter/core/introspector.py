# core/introspector.py

import inspect
from typing import Any, Dict, List

def generate_schema_for_method(method: object) -> Dict[str, Any]:
    """Generates a JSON Schema-like dictionary for a given method."""
    docstring = inspect.getdoc(method) or "No description available."
    signature = inspect.signature(method)
    
    properties = {}
    required = []
    
    # Analyze each parameter in the method's signature
    for name, param in signature.parameters.items():
        # Ignore special parameters
        if name in ('self', 'kwargs', 'args', 'async_req', 'preload_content', '_request_timeout', '_return_http_data_only'):
            continue
            
        # Map Python types to JSON Schema types
        param_type = "string" # Default
        if param.annotation in (int, float):
            param_type = "number"
        elif param.annotation == bool:
            param_type = "boolean"
        
        properties[name] = {"type": param_type}
        
        # If a parameter has no default value, it's required
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "description": docstring.split('\n')[0],
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }

def discover_tools(client_instance: object, class_path_str: str) -> List[Dict[str, Any]]:
    """Discovers all public methods on a client and generates schemas for them."""
    tools = []
    # inspect.getmembers finds all members (methods, attributes, etc.) of an object
    for name, method in inspect.getmembers(client_instance, inspect.ismethod):
        # We only care about public methods, which don't start with an underscore
        if not name.startswith('_'):
            # Create a unique tool name, e.g., "kubernetes_client_CoreV1Api.list_pod_for_all_namespaces"
            tool_name = f"{class_path_str.replace('.', '_')}.{name}"
            
            schema = generate_schema_for_method(method)
            schema['name'] = tool_name
            tools.append(schema)
            
    return tools