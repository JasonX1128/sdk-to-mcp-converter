# main.py

import yaml
import importlib
from fastapi import FastAPI
from typing import Dict, Any, List

# Import our new introspector function
from core.introspector import discover_tools

state: Dict[str, Any] = {}

app = FastAPI(
    title="SDK-to-MCP Converter",
    description="A server that dynamically exposes Python SDKs as tools for AI agents.",
    version="0.1.0",
)

def load_configuration(config_path: str = "config.yaml"):
    print(f"Loading configuration from: {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    state["config"] = config
    print("Configuration loaded successfully.")

def initialize_sdk_clients():
    print("Initializing SDK clients...")
    config = state.get("config", {})
    initialized_clients = {}
    for sdk_name, sdk_config in config.get("sdks", {}).items():
        factory_path = sdk_config["client_factory"]["path"]
        parts = factory_path.split('.')
        module_path = ".".join(parts[:-1])
        func_name = parts[-1]
        module = importlib.import_module(module_path)
        factory_func = getattr(module, func_name)
        clients = factory_func(sdk_config["classes_to_expose"])
        initialized_clients.update(clients)
    state["initialized_clients"] = initialized_clients
    print(f"Total initialized clients: {len(initialized_clients)}")

def generate_tool_schemas():
    """
    Introspects the initialized clients to generate tool schemas.
    """
    print("Generating tool schemas...")
    all_tools = []
    initialized_clients = state.get("initialized_clients", {})
    for class_path_str, client_instance in initialized_clients.items():
        tools = discover_tools(client_instance, class_path_str)
        all_tools.extend(tools)
    
    # Store the generated schemas in our state
    state["tool_schemas"] = all_tools
    print(f"Generated {len(all_tools)} tool schemas.")

@app.on_event("startup")
async def startup_event():
    """This function runs when the server starts."""
    load_configuration()
    initialize_sdk_clients()
    generate_tool_schemas() # <-- Our new step

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": f"Server is running with {len(state.get('tool_schemas', []))} tools available.",
    }

@app.get("/tools", response_model=List[Dict[str, Any]])
def get_tools():
    """Endpoint to list all available tools and their schemas."""
    return state.get("tool_schemas", [])