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
    A recursive helper function that walks through nested operations groups.
    **FIXED**: Now correctly separates guided and auto-discovery paths.
    """
    tools = []
    
    # --- Guided Discovery Path ---
    if "operations_groups" in config:
        # If we are in guided mode, we ONLY explore what's specified in the config.

        # 1. Discover methods specified for the CURRENT level, if any.
        if "include_methods" in config:
            include_methods = config.get("include_methods")
            for name, method in inspect.getmembers(current_object, inspect.ismethod):
                if not name.startswith('_') and (include_methods is None or name in include_methods):
                    tool_name = f"{name_prefix}__{name}"
                    schema = generate_schema_for_method(method)
                    schema['function']['name'] = tool_name
                    tools.append(schema)

        # 2. Recurse ONLY into the specified sub-groups.
        for group_config in config.get("operations_groups", []):
            group_name = group_config.get("name")
            if not group_name: continue
            
            sub_object = getattr(current_object, group_name, None)
            if sub_object:
                new_prefix = f"{name_prefix}__{group_name}"
                tools.extend(_discover_tools_recursive(sub_object, group_config, new_prefix))
        
    # --- Auto-Discovery Path ---
    else:
        # If no 'operations_groups' are specified, we explore everything.
        
        # 1. Discover all public methods at the current level.
        include_methods = config.get("include_methods")
        for name, method in inspect.getmembers(current_object, inspect.ismethod):
            if not name.startswith('_') and (include_methods is None or name in include_methods):
                tool_name = f"{name_prefix}__{name}"
                schema = generate_schema_for_method(method)
                schema['function']['name'] = tool_name
                tools.append(schema)
        
        # 2. Recurse into ALL discovered sub-clients.
        for name, member in inspect.getmembers(current_object):
            if (not name.startswith('_') and 
                not inspect.isroutine(member) and 
                not inspect.isclass(member) and
                not inspect.ismodule(member) and
                hasattr(member, '__dict__')):
                
                new_prefix = f"{name_prefix}__{name}"
                tools.extend(_discover_tools_recursive(member, {}, new_prefix))

    return tools

def discover_tools(client_instance: object, class_path_str: str, class_config: Dict) -> List[Dict[str, Any]]:
    """
    Discovers all tools by initiating the recursive discovery process.
    """
    name_prefix = class_config.get("alias", class_path_str.replace('.', '_'))
    return _discover_tools_recursive(client_instance, class_config, name_prefix)
