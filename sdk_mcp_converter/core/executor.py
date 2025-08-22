# core/executor.py

from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from itertools import islice

# --- Custom Exception for Timeouts ---
class ToolTimeoutError(Exception):
    """Custom exception raised when a tool call exceeds its execution time limit."""
    pass

# --- Global Settings ---
executor = ThreadPoolExecutor(max_workers=10)
EXECUTION_TIMEOUT_SECONDS = 10
SERIALIZATION_LIMIT = 30 # Max number of items to return from an iterator

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

def _execute_and_serialize(method_to_call, **kwargs):
    """
    A helper function that runs the SDK method, limits paginated results,
    and serializes the final data.
    """
    result = method_to_call(**kwargs)
    
    metadata = {"truncated": False}
    
    # Check if the result is a paginated iterator that needs to be limited.
    if hasattr(result, '__iter__') and not isinstance(result, (list, dict, str)):
        print(f"Detected a paginated/iterable result. Limiting to first {SERIALIZATION_LIMIT} items.")
        
        # Take one more than the limit to see if there are more pages.
        limited_result = list(islice(result, SERIALIZATION_LIMIT + 1))
        
        if len(limited_result) > SERIALIZATION_LIMIT:
            metadata["truncated"] = True
            # Return only the limited number of items.
            final_result_list = limited_result[:SERIALIZATION_LIMIT]
        else:
            final_result_list = limited_result
        
        serialized_data = serialize_result(final_result_list)
    else:
        # For non-iterable results, just serialize them directly.
        serialized_data = serialize_result(result)
        
    # Return a dictionary containing both the result and our metadata.
    return {"result": serialized_data, "_mcp_metadata": metadata}


def execute_tool(
    tool_name: str, 
    arguments: Dict[str, Any], 
    initialized_clients: Dict[str, Any],
    alias_map: Dict[str, str] 
) -> Any:
    """
    Finds and executes the appropriate SDK method in a separate thread with a timeout.
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

    print(f"Executing tool: {tool_name} with args: {arguments} (Timeout: {EXECUTION_TIMEOUT_SECONDS}s)")
    
    try:
        future = executor.submit(_execute_and_serialize, method_to_call, **arguments)
        return future.result(timeout=EXECUTION_TIMEOUT_SECONDS)
    except TimeoutError:
        print(f"SERVER-SIDE TIMEOUT for tool {tool_name}")
        raise ToolTimeoutError(f"Tool execution timed out on the server after {EXECUTION_TIMEOUT_SECONDS} seconds.")
    except Exception as e:
        print(f"Error executing tool {tool_name}: {e}")
        raise e
