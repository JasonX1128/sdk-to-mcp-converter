# core/introspector.py

import inspect
from typing import Any, Dict, List

def generate_schema_for_method(method: object) -> Dict[str, Any]:
    """Generates an OpenAI-compatible JSON schema for a given method."""
    docstring = inspect.getdoc(method) or "No description available."
    signature = inspect.signature(method)
    
    properties = {}
    required = []
    
    excluded_params = {'self', 'kwargs', 'args', 'async_req', 'preload_content', 
                       '_request_timeout', '_return_http_data_only', 'custom_headers'}
    
    for name, param in signature.parameters.items():
        if name in excluded_params:
            continue
            
        param_type = "string"
        if param.annotation in (int, float, 'int', 'float'):
            param_type = "number"
        elif param.annotation in (bool, 'bool'):
            param_type = "boolean"
        elif param.annotation in (list, dict, 'list', 'dict'):
            param_type = "object"
            
        properties[name] = {"type": param_type, "description": ""}
        
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "description": docstring.split('\n')[0],
            "name": "", 
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }

def discover_tools(client_instance: object, class_path_str: str, class_config: Dict) -> List[Dict[str, Any]]:
    """
    Discovers methods on a client and generates schemas.
    If 'include_methods' is present in class_config, it will only include those.
    Otherwise, it includes all public methods.
    """
    tools = []
    # Get the list of methods to explicitly include. It's None if not specified.
    include_methods = class_config.get("include_methods")

    for name, method in inspect.getmembers(client_instance, inspect.ismethod):
        if not name.startswith('_'):
            # **UPDATED FILTERING LOGIC**
            # If an 'include_methods' list exists and the current method is not in it, skip.
            # If 'include_methods' is None, this condition is false, so no methods are skipped.
            if include_methods is not None and name not in include_methods:
                continue

            tool_name = f"{class_path_str.replace('.', '_')}.{name}"
            
            schema = generate_schema_for_method(method)
            schema['function']['name'] = tool_name
            tools.append(schema)
            
    return tools
