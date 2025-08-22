# orchestrator.py
# This script connects your custom MCP server to the OpenAI API.

import requests
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Load environment variables from a .env file (for your API key)
load_dotenv()

# Initialize the OpenAI client
# The client automatically looks for the OPENAI_API_KEY environment variable.
try:
    client = OpenAI()
except Exception as e:
    print("Error: Failed to initialize OpenAI client.")
    print("Please ensure your OPENAI_API_KEY is set in a .env file.")
    print(f"Details: {e}")
    exit()


# The URL of your running MCP server
MCP_SERVER_URL = "http://127.0.0.1:8000"

# --- CORE FUNCTIONS ---

def get_tools_from_mcp() -> list:
    """
    Fetches the tool manifest from our MCP server's /tools endpoint.
    This provides the schemas needed for the OpenAI API call.
    """
    tools_url = f"{MCP_SERVER_URL}/tools"
    print(f"Fetching tool manifest from {tools_url}...")
    try:
        response = requests.get(tools_url)
        # Raise an exception if the server returned an error (e.g., 404, 500)
        response.raise_for_status()
        # The MCP server provides the schemas in the exact format OpenAI needs
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"\n--- ERROR ---")
        print(f"Could not connect to the MCP server at {MCP_SERVER_URL}.")
        print("Please ensure your MCP server is running.")
        print(f"Details: {e}")
        return []

def execute_mcp_tool(tool_name: str, arguments: dict) -> str:
    """
    Makes a POST request to our MCP server's /execute endpoint to run a tool.
    Returns the result as a JSON string.
    """
    execute_url = f"{MCP_SERVER_URL}/execute"
    print(f"Executing tool '{tool_name}' via {execute_url}...")
    try:
        payload = {"tool_name": tool_name, "arguments": arguments}
        response = requests.post(execute_url, json=payload)
        response.raise_for_status()
        # We return the result as a JSON string for the model's context
        return json.dumps(response.json())
    except requests.exceptions.RequestException as e:
        error_message = f"Error executing tool '{tool_name}': {e}"
        print(error_message)
        return json.dumps({"error": error_message})

def run_conversation_loop(available_tools: list):
    """
    Manages the main chat loop, interacting with the user and OpenAI.
    """
    # The 'messages' list stores the history of the conversation.
    messages = [
        {"role": "system", "content": "You are a helpful DevOps assistant. You have access to tools to interact with a Kubernetes cluster. Use them when necessary to answer user questions."}
    ]
    
    print("\n--- Chat with your MCP ---")
    print("Type 'exit' to end the conversation.")

    while True:
        # 1. Get user input
        user_prompt = input("You: ")
        if user_prompt.lower() == 'exit':
            print("Ending conversation.")
            break
        
        # Add user's message to the history
        messages.append({"role": "user", "content": user_prompt})

        # 2. First call to OpenAI to get the model's response or tool call
        try:
            response = client.chat.completions.create(
                model="gpt-4", # Or gpt-3.5-turbo
                messages=messages,
                tools=available_tools,
                tool_choice="auto",  # The model decides whether to call a tool
            )
        except Exception as e:
            print(f"An error occurred with the OpenAI API: {e}")
            # Remove the last user message to allow retrying
            messages.pop()
            continue

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # Add the model's response to the message history
        messages.append(response_message)

        # 3. Check if the model decided to call a tool
        if tool_calls:
            print("Assistant: The model wants to use a tool...")
            # 4. Execute the tool calls and gather results
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Use our helper function to call the MCP server
                function_response = execute_mcp_tool(
                    tool_name=function_name,
                    arguments=function_args
                )
                
                # Add the tool's result to the message history
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                )
            
            # 5. Second call to OpenAI with the tool results
            # This allows the model to generate a final, natural-language answer
            print("Assistant: Sending tool results back to the model...")
            final_response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
            )
            final_answer = final_response.choices[0].message.content
            print(f"Assistant: {final_answer}")
            messages.append(final_response.choices[0].message)
        else:
            # The model responded directly without using a tool
            print(f"Assistant: {response_message.content}")


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Step 1: Fetch the tool manifest from our running MCP server
    mcp_tools = get_tools_from_mcp()
    
    if mcp_tools:
        print(f"Successfully fetched {len(mcp_tools)} tools from the MCP server.")
        # Step 2: Start the interactive conversation loop
        run_conversation_loop(available_tools=mcp_tools)
    else:
        print("\nCould not fetch tools from the MCP server. Exiting.")

