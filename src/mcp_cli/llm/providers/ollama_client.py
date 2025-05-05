# src/llm/providers/ollama_client.py
import logging
import json
import uuid
import ollama
from typing import Any, Dict, List, Optional, Callable

# base
from mcp_cli.llm.providers.base import BaseLLMClient

class OllamaLLMClient(BaseLLMClient):
    def __init__(self, model: str = "qwen2.5-coder"):
        # set the model
        self.model = model

        # Check for AsyncClient and initialize it
        if not hasattr(ollama, "AsyncClient"):
            raise ValueError("Ollama AsyncClient not found. Please update the ollama library.")
        self.async_client = ollama.AsyncClient()

    async def create_completion(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        # Format messages for Ollama
        ollama_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]

        try:
            # Call the Ollama API using AsyncClient
            response = await self.async_client.chat(
                model=self.model,
                messages=ollama_messages,
                stream=False,
                tools=tools or [],
            )

            # Log the raw response for debugging
            logging.info(f"Ollama raw response: {response}")

            # Extract the response message and any tool calls
            message = response.get('message') # Use .get for safety
            tool_calls = []

            # Process any tool calls returned in the message
            if message and message.get('tool_calls'):
                for tool in message['tool_calls']:
                    # Ensure arguments are in string format for consistency
                    arguments = tool.get('function', {}).get('arguments')
                    if isinstance(arguments, dict):
                        arguments = json.dumps(arguments)
                    elif not isinstance(arguments, str):
                        arguments = str(arguments) if arguments is not None else '{}'
                    
                    # Check if an ID is provided; if so, preserve it; otherwise, generate one.
                    tool_call_id = tool.get("id")
                    if not tool_call_id:
                        tool_name = tool.get('function', {}).get('name', 'unknown_tool')
                        tool_call_id = f"call_{tool_name}_{str(uuid.uuid4())[:8]}"
                    
                    tool_calls.append({
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool.get('function', {}).get('name', 'unknown_tool'),
                            "arguments": arguments,
                        },
                    })

            # Return standardized response format
            return {
                "response": message.get('content', '') if message else "No response",
                "tool_calls": tool_calls,
            }
        except Exception as e:
            logging.error(f"Ollama API Error: {str(e)}", exc_info=True)
            raise ValueError(f"Ollama API Error: {str(e)}")

    async def stream_completion(self, messages: List[Dict[str, Any]]) -> None:
        """Streams the completion from Ollama using the AsyncClient."""
        ollama_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
        logging.debug(f"Starting Ollama async stream request with model: {self.model}")
        
        try:
            # Make the API call using AsyncClient and get the async stream
            stream = await self.async_client.chat(
                model=self.model,
                messages=ollama_messages,
                stream=True,
            )

            chunk_count = 0
            logging.debug("Iterating through Ollama stream...")
            
            # Asynchronously iterate through the stream
            async for chunk in stream:
                chunk_count += 1
                logging.debug(f"Received async chunk {chunk_count}: {chunk}")
                
                try:
                    content = ''
                    if isinstance(chunk, dict):
                        content = chunk.get('message', {}).get('content', '')
                        logging.debug(f"Dict access - content: {content}")
                    elif hasattr(chunk, 'message') and hasattr(chunk.message, 'content'):
                        content = chunk.message.content
                        logging.debug(f"Attribute access - content: {content}")
                    else:
                        # Fallback if structure is unexpected
                        logging.warning(f"Unexpected chunk structure: {chunk}")
                        content = str(chunk)

                    if content:
                        # Yield the content chunk instead of calling callback
                        logging.debug(f"Yielding content: {content}")
                        yield content
                    else:
                        logging.debug("No content in this chunk")

                except Exception as chunk_error:
                    logging.error(f"Error processing chunk: {chunk_error}", exc_info=True)
                    continue # Skip this chunk

            logging.debug(f"Async stream completed. Processed {chunk_count} chunks.")

        except Exception as e:
            logging.error(f"Ollama streaming API Error: {str(e)}", exc_info=True)
            # Yield an error message or raise exception
            yield f"Ollama streaming error: {str(e)}"
            # Or re-raise: raise ValueError(f"Ollama streaming API Error: {str(e)}")