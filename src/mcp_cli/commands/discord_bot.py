"""
Module for the Discord bot integration.
"""
import os
import discord
import asyncio
import logging
import re
from typing import Dict, Any
from rich import print
from mcp_cli.chat.chat_handler import handle_chat_mode
from mcp_cli.chat.chat_context import ChatContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def filter_response(response_text: str) -> str:
    """Remove <think> tags and their contents from the response."""
    # Remove <think>...</think> blocks
    filtered = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
    # Clean up any extra whitespace that might be left
    filtered = re.sub(r'\n\s*\n', '\n\n', filtered.strip())
    # If everything was filtered out, return a default message
    return filtered if filtered else "I understand, but could you please ask me something specific?"

class McpDiscordBot(discord.Client):
    def __init__(self, *, intents: discord.Intents, stream_manager: Any, **options: Any):
        super().__init__(intents=intents, **options)
        self.stream_manager = stream_manager
        self.tree = discord.app_commands.CommandTree(self)
        self.chat_context = None
        
    async def setup_chat(self):
        """Initialize the chat context."""
        provider = os.getenv("LLM_PROVIDER", "openai")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        
        # Initialize chat context
        self.chat_context = ChatContext(self.stream_manager, provider, model)
        await self.chat_context.initialize()

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')
        # Set up chat context when bot is ready
        await self.setup_chat()

    async def on_message(self, message: discord.Message):
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Check if the bot is mentioned or message is a reply to the bot
        mentioned = False
        mention_str = f'<@{self.user.id}>'
        if mention_str in message.content or (message.reference and message.reference.resolved and message.reference.resolved.author == self.user):
            mentioned = True
        
        if mentioned:
            logger.info(f"Bot mentioned by {message.author} in channel {message.channel.id}")
            
            # Extract content after mention
            content = message.content.replace(mention_str, '').strip()
            
            if not content:
                await message.channel.send("Yes? You mentioned me.", reference=message)
                return

            async with message.channel.typing():
                try:
                    if not self.chat_context:
                        await self.setup_chat()
                    
                    # Add the user's message to the conversation history
                    self.chat_context.conversation_history.append({
                        "role": "user",
                        "content": content
                    })
                    
                    while True:  # Loop to handle multiple tool calls
                        # Get response using the chat context
                        response = await self.chat_context.client.create_completion(
                            messages=self.chat_context.conversation_history,
                            tools=self.chat_context.openai_tools
                        )
                        
                        # Check for tool calls
                        tool_calls = response.get("tool_calls", [])
                        if tool_calls:
                            # Process each tool call
                            for tool_call in tool_calls:
                                try:
                                    # Get the tool name and arguments
                                    tool_name = tool_call["function"]["name"]
                                    tool_args = tool_call.get("function", {}).get("arguments", "{}")
                                    
                                    # Execute the tool call using the stream manager's call_tool method
                                    tool_result = await self.stream_manager.call_tool(tool_name, tool_args)
                                    
                                    # Add tool call and result to conversation history
                                    self.chat_context.conversation_history.append({
                                        "role": "assistant",
                                        "content": None,
                                        "tool_calls": [tool_call]
                                    })
                                    self.chat_context.conversation_history.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call["id"],
                                        "content": str(tool_result)
                                    })
                                    
                                    # Send an interim message about the tool usage
                                    await message.channel.send(f"Using tool: {tool_name}...", reference=message)
                                except Exception as e:
                                    logger.error(f"Error executing tool {tool_name}: {e}")
                                    await message.channel.send(f"Error using tool {tool_name}: {str(e)}", reference=message)
                                    # Add error result to conversation history
                                    self.chat_context.conversation_history.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call["id"],
                                        "content": f"Error: {str(e)}"
                                    })
                            
                            # Continue the loop to get the final response after tool calls
                            continue
                        
                        # If we get here, there are no more tool calls
                        # Extract and filter the response content
                        response_text = response.get("response", "No response")
                        filtered_response = filter_response(response_text)
                        
                        if filtered_response:  # Only add to history and send if there's actual content
                            # Add the filtered response to conversation history
                            self.chat_context.conversation_history.append({
                                "role": "assistant",
                                "content": filtered_response
                            })
                            
                            # Send the filtered response back to Discord
                            # Split long messages if needed (Discord has a 2000 char limit)
                            if len(filtered_response) > 1900:  # Leave room for formatting
                                chunks = [filtered_response[i:i+1900] for i in range(0, len(filtered_response), 1900)]
                                for i, chunk in enumerate(chunks):
                                    if i == 0:
                                        await message.channel.send(chunk, reference=message)
                                    else:
                                        await message.channel.send(chunk)
                            else:
                                await message.channel.send(filtered_response, reference=message)
                        
                        # Break the loop as we have the final response
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    await message.channel.send(f"Sorry, I encountered an error: {str(e)}", reference=message)


async def run_discord_bot(stream_manager: Any, **kwargs):
    """
    Initialize and run the Discord bot.
    
    Args:
        stream_manager: StreamManager instance
        **kwargs: Additional arguments passed from the command
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set.")
        print("[red]Error: DISCORD_BOT_TOKEN environment variable not set.[/red]")
        return

    # Define necessary intents
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True

    # Create and run the bot instance
    bot = McpDiscordBot(intents=intents, stream_manager=stream_manager)
    
    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.error("Failed to log in. Check the DISCORD_BOT_TOKEN.")
        print("[red]Error: Invalid Discord Bot Token. Login failed.[/red]")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"[red]An unexpected error occurred: {e}[/red]") 