# mcp_cli/chat/conversation.py
import time
import asyncio
from rich import print
import logging

# mcp cli imports
from mcp_cli.chat.tool_processor import ToolProcessor

class ConversationProcessor:
    """Class to handle LLM conversation processing."""
    
    def __init__(self, context, ui_manager):
        self.context = context
        self.ui_manager = ui_manager
        self.tool_processor = ToolProcessor(context, ui_manager)
    
    async def process_conversation(self):
        """Process the conversation loop, handling tool calls and responses.
        
        With the improved UI, we ensure clean transitions between stages
        and don't display redundant prompts.
        """
        try:
            while True:
                try:
                    start_time = time.time()
                    
                    # Use stream_manager through context if available (for better tools management)
                    if self.context.stream_manager:
                        # Access the tools data through the stream_manager
                        if not hasattr(self.context, 'openai_tools') or not self.context.openai_tools:
                            self.context.openai_tools = []
                    
                    # Send the completion request (now potentially async)
                    completion = await self.context.client.create_completion(
                        messages=self.context.conversation_history,
                        tools=self.context.openai_tools,
                    )

                    response_content = completion.get("response", "No response")
                    tool_calls = completion.get("tool_calls", [])
                    
                    # Calculate response time
                    response_time = time.time() - start_time

                    # Process tool calls if any
                    if tool_calls:
                        await self.tool_processor.process_tool_calls(tool_calls)
                        # Loop back to call create_completion again with updated history
                        continue 

                    # --- No tool calls, proceed to final response --- 
                    
                    # Placeholder for the final message content to be added to history later
                    final_response_content = None 

                    # Check if the provider is Ollama for streaming
                    if self.context.provider == 'ollama':
                        # We'll use a list to collect chunks and join them later for history
                        streamed_chunks = []

                        try:
                            logging.debug("Starting async iteration over Ollama stream")
                            # Call the async streaming completion method
                            async for chunk in self.context.client.stream_completion(
                                messages=self.context.conversation_history
                            ):
                                streamed_chunks.append(chunk)
                                # Call the UI manager to display the chunk (now synchronous)
                                await self.ui_manager.stream_assistant_chunk(chunk)
                                # Add a small sleep to allow UI to potentially update
                                await asyncio.sleep(0.01)
                            
                            logging.debug("Finished async iteration over Ollama stream")
                            
                            # Finalize the UI
                            final_response_content = "".join(streamed_chunks)
                            await self.ui_manager.finalize_assistant_response(final_response_content, response_time)
                        except Exception as e:
                            # Handle potential errors during streaming
                            logging.error(f"Error during Ollama async streaming: {e}", exc_info=True)
                            final_response_content = f"Error during streaming: {e}"
                            # Update UI with error message
                            self.ui_manager.print_assistant_response(final_response_content, response_time)
                    
                    else:
                        # --- Handle non-streaming providers (like OpenAI) --- 
                        final_response_content = response_content # Use the content from create_completion
                        # Display assistant response using the existing method
                        self.ui_manager.print_assistant_response(final_response_content, response_time)

                    # Add the final assistant message to history AFTER streaming/display
                    if final_response_content is not None:
                        self.context.conversation_history.append(
                            {"role": "assistant", "content": final_response_content}
                        )
                    
                    # Break the loop as we have the final response (streamed or not)
                    break 
                except asyncio.CancelledError:
                    # Handle cancellation during API calls
                    raise
                except Exception as e:
                    logging.error(f"Error during conversation processing: {e}", exc_info=True)
                    self.context.conversation_history.append(
                        {"role": "assistant", "content": f"I encountered an error: {str(e)}"}
                    )
                    # Display the error in the UI as well
                    self.ui_manager.print_assistant_response(f"Error: {str(e)}", 0)
                    break
        except asyncio.CancelledError:
            # Propagate cancellation up
            logging.warning("Conversation processing cancelled.")
            raise