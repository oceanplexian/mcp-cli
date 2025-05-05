# mcp_cli/commands/register_commands.py
import typer
from mcp_cli.commands import ping, chat, prompts, tools, resources, interactive, cmd
from mcp_cli.commands import discord_bot # Import the new discord bot module

# Import our improved run_command implementation
from mcp_cli.run_command import run_command
from mcp_cli.stream_manager import StreamManager
import logging
import os
from typing import Optional

def ping_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
):
    """Simple ping command."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    run_command(ping.ping_run, config_file, servers, user_specified, {"server_names": server_names})
    return 0

def chat_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = True,
    logging_level: str = "WARNING",
):
    """Interactive chat mode."""
    from mcp_cli.cli_options import process_options
    
    # Set logging level
    numeric_level = getattr(logging, logging_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid logging level: {logging_level}")
    logging.getLogger().setLevel(numeric_level)
    logging.debug(f"Logging level set to {logging_level.upper()}")
    
    # Set environment variables for provider and model
    os.environ["LLM_PROVIDER"] = provider
    os.environ["LLM_MODEL"] = model if model else "gpt-4o-mini"
    
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    run_command(chat.chat_run, config_file, servers, user_specified, {
        "server_names": server_names
    })
    return 0

def interactive_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
):
    """Enter interactive mode with a command prompt."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    # Remove extra parameter "server_names" since interactive_mode does not expect it.
    run_command(interactive.interactive_mode, config_file, servers, user_specified)
    return 0

def prompts_list_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
):
    """List available prompts."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    run_command(prompts.prompts_list, config_file, servers, user_specified, {"server_names": server_names})
    return 0

def tools_list_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
):
    """List available tools."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    run_command(tools.tools_list, config_file, servers, user_specified, {"server_names": server_names})
    return 0

def tools_call_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
):
    """Call a tool with JSON arguments."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    run_command(tools.tools_call, config_file, servers, user_specified, {"server_names": server_names})
    return 0

def resources_list_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
):
    """List available resources."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    run_command(resources.resources_list, config_file, servers, user_specified, {"server_names": server_names})
    return 0

def cmd_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
    input: str = None,
    prompt: str = None, 
    output: str = None,
    raw: bool = False,
    tool: str = None,
    tool_args: str = None,
    system_prompt: str = None,
):
    """Command mode for scriptable usage."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    
    # Merge server_names with other extra parameters
    extra_params = {
        "input": input,
        "prompt": prompt,
        "output": output,
        "raw": raw,
        "tool": tool,
        "tool_args": tool_args,
        "system_prompt": system_prompt,
        "server_names": server_names
    }
    
    run_command(cmd.cmd_run, config_file, servers, user_specified, extra_params)
    return 0

def discord_command(
    config_file: str = "server_config.json",
    server: str = None,
    provider: str = "openai",
    model: str = None,
    disable_filesystem: bool = False,
):
    """Run the Discord bot to interact with MCP servers and LLM."""
    from mcp_cli.cli_options import process_options
    servers, user_specified, server_names = process_options(server, disable_filesystem, provider, model, config_file)
    
    # Set environment variables for provider and model
    os.environ["LLM_PROVIDER"] = provider
    os.environ["LLM_MODEL"] = model if model else "gpt-4o-mini"
    
    # Use run_command utility to handle StreamManager creation/cleanup
    run_command(discord_bot.run_discord_bot, config_file, servers, user_specified, {"server_names": server_names})
    return 0

def register_commands(app: typer.Typer, process_options, run_command_func):
    """Register all commands on the provided Typer app."""
    # Note: We ignore the run_command_func parameter and use our improved version
    
    app.command("ping")(ping_command)
    app.command("chat")(chat_command)
    app.command("interactive")(interactive_command)
    app.command("cmd")(cmd_command)
    app.command("discord")(discord_command)
    
    # Create sub-typer apps for prompts, tools, and resources.
    prompts_app = typer.Typer(help="Prompts commands")
    tools_app = typer.Typer(help="Tools commands")
    resources_app = typer.Typer(help="Resources commands")
    
    prompts_app.command("list")(prompts_list_command)
    tools_app.command("list")(tools_list_command)
    tools_app.command("call")(tools_call_command)
    resources_app.command("list")(resources_list_command)
    
    app.add_typer(prompts_app, name="prompts")
    app.add_typer(tools_app, name="tools")
    app.add_typer(resources_app, name="resources")

# Export chat_command so it can be imported in main.py.
__all__ = ["register_commands", "chat_command"]
