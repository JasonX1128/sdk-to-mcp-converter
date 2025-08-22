# main.py

import yaml
import importlib
import os
import traceback
import json # <-- Import json for pretty-printing
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

from core.executor import execute_tool, ToolTimeoutError

CONFIG_FILE_PATH = os.getenv("MCP_CONFIG", "config.yaml")
state: Dict[str, Any] = {}

class ToolExecutionRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}

app = FastAPI(
    title="Mission Control Plane (MCP) for SDKs",
    description="Dynamically exposes Python SDK methods as tools for AI agents.",
    version="1.6.1", # Version bump for response logging
)

# --- Server Startup Logic (Unchanged) ---
def load_configuration(config_path: str):
    print(f"Loading configuration from: {config_path}")
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        state["config"] = config
        print("Configuration loaded.")
    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{config_path}'. Exiting.")
        exit()

def initialize_sdk_clients():
    print("Initializing SDK clients...")
    config = state.get("config", {})
    initialized_clients = {}
    alias_map = {}
    
    for sdk_name, sdk_config in config.get("sdks", {}).items():
        if not sdk_config.get("enabled", True):
            continue
            
        factory_config = sdk_config.get("client_factory", {})
        factory_path = factory_config.get("path")
        if not factory_path:
            continue

        try:
            parts = factory_path.split('.')
            module_path = ".".join(parts[:-1])
            func_name = parts[-1]
            
            module = importlib.import_module(module_path)
            factory_func = getattr(module, func_name)
            
            classes_to_expose_config = sdk_config.get("classes_to_expose", [])
            class_paths = []
            for cfg in classes_to_expose_config:
                class_path = cfg.get("class_path") if isinstance(cfg, dict) else cfg
                if class_path:
                    class_paths.append(class_path)
                    if isinstance(cfg, dict) and "alias" in cfg:
                        alias_map[cfg["alias"]] = class_path
                    else:
                        mangled_path = class_path.replace('.', '_')
                        alias_map[mangled_path] = class_path

            factory_args = sdk_config.copy()
            
            if 'client_factory' in factory_args:
                factory_args.update(factory_config)
                del factory_args['client_factory']
            if 'classes_to_expose' in factory_args:
                 del factory_args['classes_to_expose']
            if 'enabled' in factory_args:
                 del factory_args['enabled']

            clients = factory_func(classes_to_expose=class_paths, **factory_args)
            initialized_clients.update(clients)
        except Exception as e:
            print(f"Failed to initialize SDK '{sdk_name}': {e}")
            
    state["initialized_clients"] = initialized_clients
    state["alias_map"] = alias_map
    print(f"Total initialized clients: {len(initialized_clients)}")

def generate_tool_schemas():
    from core.introspector import discover_tools
    print("Generating tool schemas...")
    all_tools = []
    initialized_clients = state.get("initialized_clients", {})
    config = state.get("config", {})

    for sdk_name, sdk_config in config.get("sdks", {}).items():
        if not sdk_config.get("enabled", True):
            continue
        
        for class_config_item in sdk_config.get("classes_to_expose", []):
            class_path_str = None
            config_for_discover = {}

            if isinstance(class_config_item, dict):
                class_path_str = class_config_item.get("class_path")
                config_for_discover = class_config_item
            elif isinstance(class_config_item, str):
                class_path_str = class_config_item

            if not class_path_str:
                continue

            client_instance = initialized_clients.get(class_path_str)
            if client_instance:
                tools = discover_tools(client_instance, class_path_str, config_for_discover)
                all_tools.extend(tools)
    
    state["tool_schemas"] = all_tools
    print(f"Generated {len(all_tools)} total tool schemas.")

@app.on_event("startup")
async def startup_event():
    load_configuration(config_path=CONFIG_FILE_PATH)
    initialize_sdk_clients()
    generate_tool_schemas()

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "MCP Server is running.",
        "config_file": CONFIG_FILE_PATH,
        "available_tools": len(state.get("tool_schemas", []))
    }

@app.get("/tools", response_model=List[Dict[str, Any]])
def get_tools():
    return state.get("tool_schemas", [])

@app.post("/execute")
async def execute_tool_endpoint(request: ToolExecutionRequest):
    try:
        result_dict = execute_tool(
            tool_name=request.tool_name,
            arguments=request.arguments,
            initialized_clients=state.get("initialized_clients", {}),
            alias_map=state.get("alias_map", {})
        )
        # **NEW**: Add logging to show exactly what is being sent back.
        print("\n--- SERVER RESPONSE TO ORCHESTRATOR ---")
        print(json.dumps(result_dict, indent=2))
        print("---------------------------------------\n")
        return result_dict
    except ToolTimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        tb_str = traceback.format_exc()
        print("\n--- UNEXPECTED SERVER ERROR ---")
        print(tb_str)
        print("-----------------------------\n")
        error_detail = {
            "error_message": str(e),
            "traceback": tb_str
        }
        raise HTTPException(status_code=500, detail=error_detail)
