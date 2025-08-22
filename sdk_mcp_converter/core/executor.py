# core/executor.py

from typing import Dict, Any

def serialize_result(result: Any) -> Any:
    """Recursively serializes a complex SDK result object to a JSON-friendly format."""
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
    """Finds and executes the appropriate SDK method based on the tool name."""
    try:
        # **FIX**: Split the tool name by the new double-underscore separator.
        class_path_str_mangled, method_name = tool_name.rsplit('__', 1)
        # Reverse the mangling of the class path (replace single underscores with periods)
        class_path_str = class_path_str_mangled.replace('_', '.')
    except ValueError:
        raise ValueError(f"Invalid tool_name format: {tool_name}")

    client_instance = initialized_clients.get(class_path_str)
    if not client_instance:
        raise ValueError(f"Client for '{class_path_str}' not found.")

    method_to_call = getattr(client_instance, method_name, None)
    if not method_to_call:
        raise ValueError(f"Method '{method_name}' not found on client '{class_path_str}'.")

    print(f"Executing tool: {tool_name} with args: {arguments}")
    
    try:
        result = method_to_call(**arguments)
        return serialize_result(result)
    except Exception as e:
        print(f"Error executing tool {tool_name}: {e}")
        raise e
