# main.py

import yaml
import importlib
from fastapi import FastAPI
from typing import Dict, Any

# A simple dictionary to hold our server's state.
state: Dict[str, Any] = {}

# Create the FastAPI application instance
app = FastAPI(
    title="SDK-to-MCP Converter",
    description="A server that dynamically exposes Python SDKs as tools for AI agents.",
    version="0.1.0",
)

def load_configuration(config_path: str = "config.yaml"):
    """Reads the YAML configuration file from disk."""
    print(f"Loading configuration from: {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    state["config"] = config
    print("Configuration loaded successfully.")

def initialize_sdk_clients():
    """
    Uses the loaded config to find and run the client factory for each SDK.
    """
    print("Initializing SDK clients...")
    config = state.get("config", {})
    initialized_clients = {}

    for sdk_name, sdk_config in config.get("sdks", {}).items():
        factory_path = sdk_config["client_factory"]["path"]
        
        # Dynamically import the factory function from its path
        parts = factory_path.split('.')
        module_path = ".".join(parts[:-1])
        func_name = parts[-1]
        
        module = importlib.import_module(module_path)
        factory_func = getattr(module, func_name)
        
        # Run the factory function and store the resulting clients
        clients = factory_func(sdk_config["classes_to_expose"])
        initialized_clients.update(clients)

    state["initialized_clients"] = initialized_clients
    print(f"Total initialized clients: {len(initialized_clients)}")


@app.on_event("startup")
async def startup_event():
    """This function runs when the server starts."""
    load_configuration()
    initialize_sdk_clients()


@app.get("/")
def read_root():
    """Health check endpoint."""
    # We remove the config from the response for brevity
    return {
        "status": "ok",
        "message": f"Server is running with {len(state.get('initialized_clients', []))} clients initialized.",
    }