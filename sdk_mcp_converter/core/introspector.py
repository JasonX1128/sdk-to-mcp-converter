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
                       '_request_timeout', '_return_http_data_only', 'custom_headers',
                       'visibility'}
    
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

def _discover_tools_recursive(current_object: object, config: Dict, name_prefix: str) -> List[Dict[str, Any]]:
    """
    A recursive helper function to walk through nested operations groups.
    """
    tools = []
    
    # Get the include_methods list, which will be None if the key doesn't exist.
    include_methods = config.get("include_methods")

    # Discover methods at the current level. Runs regardless of whether
    # 'include_methods' is present in the config.
    for name, method in inspect.getmembers(current_object, inspect.ismethod):
        if not name.startswith('_'):
            # The condition 'include_methods is None' correctly handles the case
            # where the key is omitted, including all public methods by default.
            if include_methods is None or name in include_methods:
                tool_name = f"{name_prefix}__{name}"
                schema = generate_schema_for_method(method)
                schema['function']['name'] = tool_name
                tools.append(schema)

    # Recursive Step: Discover methods in nested groups
    if "operations_groups" in config:
        for group_config in config["operations_groups"]:
            group_name = group_config["name"]
            sub_object = getattr(current_object, group_name, None)
            if sub_object:
                new_prefix = f"{name_prefix}__{group_name}"
                nested_tools = _discover_tools_recursive(sub_object, group_config, new_prefix)
                tools.extend(nested_tools)
                
    return tools

def discover_tools(client_instance: object, class_path_str: str, class_config: Dict) -> List[Dict[str, Any]]:
    """
    Discovers all tools by initiating the recursive discovery process.
    """
    name_prefix = class_config.get("alias", class_path_str.replace('.', '_'))
    return _discover_tools_recursive(client_instance, class_config, name_prefix)
