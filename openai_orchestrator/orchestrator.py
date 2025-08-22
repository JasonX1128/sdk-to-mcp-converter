# orchestrator.py
# This script connects your custom MCP server to the OpenAI API.

import requests
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

try:
    client = OpenAI()
except Exception as e:
    print("Error: Failed to initialize OpenAI client.")
    print("Please ensure your OPENAI_API_KEY is set in a .env file.")
    print(f"Details: {e}")
    exit()

MCP_SERVER_URL = "http://127.0.0.1:8000"
MCP_REQUEST_TIMEOUT = 15

# --- CORE FUNCTIONS ---

def get_tools_from_mcp() -> list:
    """Fetches the tool manifest from our MCP server's /tools endpoint."""
    tools_url = f"{MCP_SERVER_URL}/tools"
    print(f"Fetching tool manifest from {tools_url}...")
    try:
        response = requests.get(tools_url, timeout=MCP_REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"\n--- ERROR ---")
        print(f"Could not connect to the MCP server at {MCP_SERVER_URL}.")
        print("Please ensure your MCP server is running.")
        print(f"Details: {e}")
        return []

def execute_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """
    Makes a POST request to our MCP server's /execute endpoint to run a tool.
    **FIXED**: Now correctly handles and parses detailed error responses from the server.
    """
    execute_url = f"{MCP_SERVER_URL}/execute"
    print(f"Executing tool '{tool_name}' via {execute_url}...")
    try:
        payload = {"tool_name": tool_name, "arguments": arguments}
        response = requests.post(execute_url, json=payload, timeout=MCP_REQUEST_TIMEOUT)

        # This is more reliable than only relying on raise_for_status().
        if response.status_code != 200:
            try:
                # Attempt to parse the detailed error from the server.
                error_detail = response.json().get("detail", response.text)
                if isinstance(error_detail, dict):
                    error_message = f"Error executing tool '{tool_name}': {error_detail.get('error_message')}\n\n[SERVER TRACEBACK]\n{error_detail.get('traceback')}"
                else:
                    error_message = f"Error executing tool '{tool_name}': {error_detail}"
            except json.JSONDecodeError:
                # Fallback if the error response is not valid JSON.
                error_message = f"Error executing tool '{tool_name}': {response.status_code} {response.reason}"
            
            print(error_message)
            return {"error": error_message}

        # If the request was successful, return the JSON.
        return response.json()

    except requests.exceptions.RequestException as e:
        # This will now primarily catch connection errors or timeouts.
        error_message = f"Error executing tool '{tool_name}': {e}"
        print(error_message)
        return {"error": error_message}

def run_conversation_loop(available_tools: list):
    """Manages the main chat loop, interacting with the user and OpenAI."""
    messages = [
        {"role": "system", "content": "You are a helpful DevOps assistant. You have access to tools to interact with various services. If a tool call fails and you receive a server traceback, analyze the traceback to understand the root cause of the error. Use this information to correct your tool call parameters or to inform the user about the underlying issue in the SDK or tool configuration."}
    ]
    
    print("\n--- Chat with your MCP ---")
    print("Type 'exit' to end the conversation.")

    while True:
        user_prompt = input("You: ")
        if user_prompt.lower() == 'exit':
            break
        
        messages.append({"role": "user", "content": user_prompt})

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=available_tools,
                tool_choice="auto",
            )
            usage = response.usage
            print(f"[OpenAI Usage] Request: {usage.prompt_tokens} tokens, Response: {usage.completion_tokens} tokens")

        except Exception as e:
            print(f"An error occurred with the OpenAI API: {e}")
            messages.pop()
            continue

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        messages.append(response_message)

        if tool_calls:
            print("Assistant: The model wants to use a tool...")
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                function_response_dict = execute_mcp_tool(
                    tool_name=function_name,
                    arguments=function_args
                )
                
                result_content = json.dumps(function_response_dict)
                
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": result_content,
                    }
                )
            
            print("Assistant: Sending tool results back to the model...")
            final_response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
            )
            final_usage = final_response.usage
            print(f"[OpenAI Usage] Request: {final_usage.prompt_tokens} tokens, Response: {final_usage.completion_tokens} tokens")

            final_answer = final_response.choices[0].message.content
            print(f"Assistant: {final_answer}")
            messages.append(final_response.choices[0].message)
        else:
            print(f"Assistant: {response_message.content}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    mcp_tools = get_tools_from_mcp()
    
    if mcp_tools:
        print(f"Successfully fetched {len(mcp_tools)} tools from the MCP server.")
        run_conversation_loop(available_tools=mcp_tools)
    else:
        print("\nCould not fetch tools from the MCP server. Exiting.")
