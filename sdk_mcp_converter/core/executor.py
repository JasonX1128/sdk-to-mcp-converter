# core/executor.py

from typing import Dict, Any

def serialize_result(result: Any) -> Any:
    """Recursively serializes a complex SDK result object to a JSON-friendly format."""
    if hasattr(result, '__iter__') and not isinstance(result, (list, dict, str)):
        result = list(result)

    if hasattr(result, 'to_dict'):
        return result.to_dict()
    
    if isinstance(result, list):
        return [serialize_result(item) for item in result]
    
    if isinstance(result, dict):
        return {k: serialize_result(v) for k, v in result.items()}
        
    if not isinstance(result, (str, int, float, bool)) and result is not None:
        try:
            return str(result)
        except Exception:
            return "Unserializable Object"
            
    return result

def execute_tool(
    tool_name: str, 
    arguments: Dict[str, Any], 
    initialized_clients: Dict[str, Any],
    # **FIX**: Add the 'alias_map' parameter to the function signature.
    alias_map: Dict[str, str] 
) -> Any:
    """
    Finds and executes the appropriate SDK method using an alias map.
    """
    try:
        parts = tool_name.split('__')
        alias = parts[0]
        object_path = parts[1:-1]
        method_name = parts[-1]
        
        class_path_str = alias_map.get(alias)
        if not class_path_str:
             raise ValueError(f"No client found for alias '{alias}'.")

    except (IndexError, ValueError) as e:
        raise ValueError(f"Invalid tool_name format or alias: {tool_name} ({e})")

    current_object = initialized_clients.get(class_path_str)
    if not current_object:
        raise ValueError(f"Client for '{class_path_str}' not found.")

    for part in object_path:
        current_object = getattr(current_object, part, None)
        if not current_object:
            raise ValueError(f"Nested object '{part}' not found in tool path '{tool_name}'.")

    method_to_call = getattr(current_object, method_name, None)
    if not method_to_call:
        raise ValueError(f"Method '{method_name}' not found on target object.")

    print(f"Executing tool: {tool_name} with args: {arguments}")
    
    try:
        result = method_to_call(**arguments)
        return serialize_result(result)
    except Exception as e:
        print(f"Error executing tool {tool_name}: {e}")
        raise e
