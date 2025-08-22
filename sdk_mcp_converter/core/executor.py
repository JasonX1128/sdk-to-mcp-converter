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
    initialized_clients: Dict[str, Any]
) -> Any:
    """
    Finds and executes the appropriate SDK method by walking down the object path
    for arbitrarily nested tool names.
    """
    try:
        # Split the tool name into all its parts
        # e.g., 'Client__Group1__Group2__Method' -> ['Client', 'Group1', 'Group2', 'Method']
        parts = tool_name.split('__')
        class_path_str_mangled = parts[0]
        object_path = parts[1:-1] # The nested groups, e.g., ['Group1', 'Group2']
        method_name = parts[-1]   # The final method name
        
        class_path_str = class_path_str_mangled.replace('_', '.')
    except IndexError:
        raise ValueError(f"Invalid tool_name format: {tool_name}")

    # Start with the top-level client instance
    current_object = initialized_clients.get(class_path_str)
    if not current_object:
        raise ValueError(f"Client for '{class_path_str}' not found.")

    # Iteratively walk down the object path to get to the final target object
    for part in object_path:
        current_object = getattr(current_object, part, None)
        if not current_object:
            raise ValueError(f"Nested object '{part}' not found in tool path '{tool_name}'.")

    # Get the actual method from the final object
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
