import asyncio
from pathlib import Path

from dotenv import load_dotenv

import System_prompt
from pypdf import PdfReader
import requests
from pydantic import BaseModel
import utilities
from agents import Agent, Runner, trace
from AutoReply_Servers import AutoReplayServer


def evaluator_user_prompt(reply, message, history):
    user_prompt = f"Here's the conversation between the User and the Agent: \n\n{history}\n\n"
    user_prompt += f"Here's the latest message from the User: \n\n{message}\n\n"
    user_prompt += f"Here's the latest response from the Agent: \n\n{reply}\n\n"
    user_prompt += "Please evaluate the response, replying with whether it is acceptable and your feedback."
    return user_prompt


def evaluate(reply, message, history,linkedin,name) -> utilities.Evaluation:
    evaluator_system_prompt = evaluator_system_prompt.format(NAME=name, linkedin=linkedin)
    return rgemini_ask(evaluator_system_prompt, evaluator_user_prompt(reply, message, history))


def chat(message,system_prompt, history):
    results = utilities.ollama_ask(system_prompt, message)
    return results

def feedback_chat(message, history):
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=messages)
    reply =response.choices[0].message.content

    evaluation = evaluate(reply, message, history)
    
    if evaluation.is_acceptable:
        print("Passed evaluation - returning reply")
    else:
        print("Failed evaluation - retrying")
        print(evaluation.feedback)
        reply = rerun(reply, message, history, evaluation.feedback)       
    return reply

def rerun(reply, message, history, feedback):
    updated_system_prompt = System_prompt.system_prompt + "\n\n## Previous answer rejected\nYou just tried to reply, but the quality control rejected your reply\n"
    updated_system_prompt += f"## Your attempted answer:\n{reply}\n\n"
    updated_system_prompt += f"## Reason for rejection:\n{feedback}\n\n"
    return ollama_ask(updated_system_prompt, message)

async def main():
    # Create the server instance
    server = AutoReplayServer("AutoReplayServer")
    load_dotenv(override=True)
    
    # Create system prompt
    mcp_tools = await utilities.list_auto_response_tools(server)
    #print(mcp_tools)
    openai_tools = await utilities.get_auto_response_tools_openai(server)
    print(openai_tools)
    instructions = utilities.construct_system_prompt("Ahmed Abdelfattah")
    # Create agent with MCP server
    agent = Agent(
        name="Auto_Replay",
        instructions=instructions,
        model=System_prompt.model,
        tools=openai_tools
    )
    
    # Run the agent
    with trace("Auto_Replay"):
        result = await Runner.run(agent, System_prompt.request)
        print(result)
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())

