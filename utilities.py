from pathlib import Path
from System_prompt import system_prompt, evaluator_system_prompt
from pypdf import PdfReader
import requests
from pydantic import BaseModel
import os
from openai import OpenAI
import System_prompt
from AutoReply_Servers import AutoReplayServer
from agents import FunctionTool
import json
from dotenv import load_dotenv

load_dotenv(override=True)
class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str
ollama_api_key = os.getenv('OPENAI_API_KEY')
if not ollama_api_key:
    raise RuntimeError(
        "Missing OLLAMA_API_KEY. Create a key at https://ollama.com/settings/keys "
        "and set it in your environment."
    )

url = "https://ollama.com/api/web_search"
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
gemini = OpenAI(
    api_key=OPENAI_API_KEY, 
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


def gemini_ask(system_prompt: str, message: str, history) -> Evaluation:
    messages = [{"role": "system", "content": system_prompt}] + [{"role": "user", "content": message}]
    response = gemini.beta.chat.completions.parse(model="gemini-2.5-flash", messages=messages, response_format=Evaluation)
    return response.choices[0].message.parsed

def ollama_ask(system_prompt: str, message: str, *, max_results: int = 1) -> list[dict[str, any]]:
    query =  system_prompt + "The user's message is: " + message
    payload = {"query": query, "max_results": max_results}
    headers = {"Authorization": f"Bearer {ollama_api_key}"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to call Ollama web_search API. Original error: {e}") from e

    data = resp.json()
    results = data.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError("Unexpected response from Ollama web_search API (missing 'results' list).")
    return results

def construct_system_prompt(name: str) -> str:
    system_prompt = System_prompt.system_prompt.format(NAME=name)
    return system_prompt

async def list_auto_response_tools(server:AutoReplayServer):
    tools_result = await server.get_mcp_server().list_tools()
    return tools_result

async def call_auto_response_tool(server:AutoReplayServer,tool_name, tool_args):
    result = await server.get_mcp_server().call_tool(tool_name, tool_args)
    return result

async def get_auto_response_tools_openai(server:AutoReplayServer):
    openai_tools = []
    for tool in await list_auto_response_tools(server):
        schema = {**tool.inputSchema, "additionalProperties": False}
        openai_tool = FunctionTool(
            name=tool.name,
            description=tool.description,
            params_json_schema=schema,
            on_invoke_tool=lambda ctx, args, toolname=tool.name: call_auto_response_tool(server,toolname, json.loads(args))
                
        )
        openai_tools.append(openai_tool)
    return openai_tools