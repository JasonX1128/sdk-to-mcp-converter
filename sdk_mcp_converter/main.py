# main.py

import yaml
import importlib
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file at the very beginning.
load_dotenv()

from core.introspector import discover_tools
from core.executor import execute_tool

# --- Configuration Setup ---
# Read the config file path from an environment variable.
CONFIG_FILE_PATH = os.getenv("MCP_CONFIG", "config.yaml")


# --- Standard Setup ---
state: Dict[str, Any] = {}

class ToolExecutionRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}

app = FastAPI(
    title="Mission Control Plane (MCP) for SDKs",
    description="Dynamically exposes Python SDK methods as tools for AI agents.",
    version="1.3.3", # Version bump for bugfix
)

# --- Server Startup Logic ---
def load_configuration(config_path: str):
    """Loads and parses the specified YAML configuration file."""
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
    """Dynamically calls the factory function for each configured SDK."""
    print("Initializing SDK clients...")
    config = state.get("config", {})
    initialized_clients = {}
    for sdk_name, sdk_config in config.get("sdks", {}).items():
        if not sdk_config.get("enabled", True):
            print(f"Skipping disabled SDK: {sdk_name}")
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
                if isinstance(cfg, dict):
                    class_paths.append(cfg.get("class_path"))
                elif isinstance(cfg, str):
                    class_paths.append(cfg)
            
            class_paths = [path for path in class_paths if path]

            # Prepare arguments for the factory function
            factory_args = sdk_config.copy()
            factory_args["classes_to_expose"] = class_paths

            # **FIX**: Merge the nested client_factory dictionary into the main arguments.
            # This ensures keys like 'auth_env_var' are passed correctly.
            if 'client_factory' in factory_args:
                factory_args.update(factory_config)
                del factory_args['client_factory'] # Clean up the original nested dict

            clients = factory_func(**factory_args)
            initialized_clients.update(clients)
        except Exception as e:
            print(f"Failed to initialize SDK '{sdk_name}': {e}")
            
    state["initialized_clients"] = initialized_clients
    print(f"Total initialized clients: {len(initialized_clients)}")

def generate_tool_schemas():
    """Introspects initialized clients to generate schemas based on config."""
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
    """Runs all initialization steps when the server starts."""
    load_configuration(config_path=CONFIG_FILE_PATH)
    initialize_sdk_clients()
    generate_tool_schemas()

# --- API Endpoints (Unchanged) ---
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
        result = execute_tool(
            tool_name=request.tool_name,
            arguments=request.arguments,
            initialized_clients=state.get("initialized_clients", {})
        )
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during tool execution: {str(e)}")
