# mcp_cli/chat/ui_manager.py
import os
import json
import time
import asyncio
from rich import print
from rich.markdown import Markdown
from rich.panel import Panel
from rich.console import Console
from rich.live import Live
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style

# mcp cli imports
from mcp_cli.chat.command_completer import ChatCommandCompleter
from mcp_cli.chat.commands import handle_command

class ChatUIManager:
    """Class to manage the chat UI interface."""
    
    def __init__(self, context):
        self.context = context
        self.console = Console()
        self.verbose_mode = False  # Default to compact mode
        self.tool_calls = []  # For tracking tool calls in compact mode
        self.live_display = None  # For animated tool calls
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self.tool_start_time = None  # For timing tool execution
        self.current_tool_start_time = None  # For timing individual tool
        self.tools_running = False  # Flag to track if tools are currently running
        self.interrupt_requested = False  # Flag to track if user requested interrupt
        self.tool_times = []  # List to track time taken by each tool
        self.last_input = None  # Store the last input
        self.assistant_live = None # Rich Live instance for streaming response
        self.current_assistant_text = Text() # Text object for streaming
        
        # Set up prompt_toolkit session with history and tab completion
        history_file = os.path.expanduser("~/.mcp_chat_history")
        self.style = Style.from_dict({
            # Don't highlight the completion menu background
            'completion-menu': 'bg:default',
            'completion-menu.completion': 'bg:default fg:goldenrod',
            'completion-menu.completion.current': 'bg:default fg:goldenrod bold',
            # Set auto-suggestion color to a very subtle shade
            'auto-suggestion': 'fg:ansibrightblack',
        })
        
        self.session = PromptSession(
            history=FileHistory(history_file),
            auto_suggest=AutoSuggestFromHistory(),
            completer=ChatCommandCompleter(context.to_dict()),
            complete_while_typing=True,
            style=self.style,
            message="> "  # Simple plain prompt
        )
    
    async def get_user_input(self):
        """Get user input with a simple prompt."""
        # Just use the built-in session prompt
        user_message = await self.session.prompt_async()
        
        # Store the input
        self.last_input = user_message.strip()
        
        # Clear the line to remove the input
        print("\r" + " " * (len(self.last_input) + 2), end="\r")
        
        return self.last_input
    
    def print_user_message(self, message):
        """Print formatted user message."""
        user_panel_text = message if message else "[No Message]"
        print(Panel(user_panel_text, style="bold yellow", title="You"))
        # Reset tool calls for new conversation turn
        self.tool_calls = []
        # Start with a clean display
        if not self.verbose_mode:
            self.live_display = None
    
    def print_tool_call(self, tool_name, raw_arguments):
        """Print formatted tool call."""
        # Initialize timer on first tool call
        if not self.tool_start_time:
            self.tool_start_time = time.time()
            self.tools_running = True
        
        # If this isn't the first tool, record the time for the previous tool
        if self.current_tool_start_time and self.tool_calls:
            elapsed = time.time() - self.current_tool_start_time
            self.tool_times.append(elapsed)
        
        # Start timer for this tool
        self.current_tool_start_time = time.time()
        
        # Handle JSON arguments
        if isinstance(raw_arguments, str):
            try:
                raw_arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                # If it's not valid JSON, just display as is
                pass

        # Format as JSON
        tool_args_str = json.dumps(raw_arguments, indent=2)
        
        # Store tool call for compact mode
        self.tool_calls.append({
            "name": tool_name,
            "args": raw_arguments
        })
        
        # Check if interrupt was requested
        if self.interrupt_requested:
            print("\n[bold red]Tool execution interrupted by user![/bold red]")
            # Reset flags
            self.interrupt_requested = False
            self.tools_running = False
            self.tool_start_time = None
            self.current_tool_start_time = None
            self.tool_times = []
            # You would need to implement actual interruption logic here
            # This might require changes to your async conversation processor
            return
        
        if self.verbose_mode:
            # Verbose mode - show full panel
            tool_md = f"**Tool Call:** {tool_name}\n\n```json\n{tool_args_str}\n```"
            print(Panel(Markdown(tool_md), style="bold magenta", title="Tool Invocation"))
        else:
            # Compact mode - show animated tool calls
            self._display_compact_tool_calls()
    
    def _get_spinner_char(self):
        """Get the next character in the spinner animation."""
        char = self.spinner_frames[self.spinner_idx]
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_frames)
        return char
    
    def _display_compact_tool_calls(self):
        """Display tool calls in a compact, animated format on a single line."""
        if self.live_display is None:
            # Start a new live display with higher refresh rate for accurate timer
            self.live_display = Live("", refresh_per_second=4, console=self.console)
            self.live_display.start()
            # Print interrupt hint below the live display
            print("[dim italic]Press Ctrl+C to interrupt tool execution[/dim italic]", end="\r")
        
        # Calculate elapsed time - recalculate each time to ensure accuracy
        current_time = time.time()
        current_tool_elapsed = int(current_time - self.current_tool_start_time)
        total_elapsed_seconds = int(current_time - self.tool_start_time)
        current_tool_elapsed_str = f"{current_tool_elapsed}s"
        total_elapsed_str = f"{total_elapsed_seconds}s"
        
        # Create a text representation showing each step
        spinner_char = self._get_spinner_char()
        current_tools = []
        
        # Show all completed tools with their timing - using dim color for less emphasis
        for i, tool in enumerate(self.tool_calls[:-1]):
            if i < len(self.tool_times):
                time_str = f" ({self.tool_times[i]:.1f}s)"
            else:
                time_str = ""
            current_tools.append(f"[dim green]{i+1}. {tool['name']}{time_str}[/dim green]")
        
        # Show current tool with spinner and current timing - using less bright colors
        current_tool = self.tool_calls[-1]
        current_idx = len(self.tool_calls) - 1
        current_tools.append(f"[magenta]{current_idx+1}. {current_tool['name']} ({current_tool_elapsed_str})[/magenta]")
        
        # Build the display text - using muted colors overall
        tool_text = " → ".join(current_tools)
        display_text = Text.from_markup(f"[dim]Calling tools (total: {total_elapsed_str}): {spinner_char}[/dim] {tool_text}")
        
        # Update the live display
        self.live_display.update(display_text)
    
    def print_assistant_response(self, response_content, response_time):
        """Print formatted assistant response (NON-STREAMING)."""
        # Ensure any previous tool or streaming display is stopped
        self._stop_tool_display()
        # self._stop_streaming_display() # No longer needed here

        # Prepare and print the final panel for non-streamed responses
        self._print_final_assistant_panel(response_content, response_time)

    async def stream_assistant_chunk(self, chunk: str):
        """Print a chunk directly to the console during streaming."""
        # Ensure tool display is stopped before starting streaming display
        self._stop_tool_display()

        # Print a header only on the first chunk
        if not hasattr(self, '_streaming_header_printed'):
            self.console.print("[bold purple]Assistant:[/bold purple]")
            self._streaming_header_printed = True

        # Print the chunk directly without newline
        self.console.print(chunk, end="")
        # We might need a flush here if console doesn't auto-flush
        # self.console.file.flush() # Try adding if needed

    async def finalize_assistant_response(self, full_content: str, response_time: float):
        """Finalize the assistant response display after streaming."""
        # Stop the tool display (streaming display is already stopped implicitly)
        self._stop_tool_display()

        # Print a newline to finish the streamed output
        self.console.print()

        # Print the response time footer
        footer = f"Response time: {response_time:.2f}s"
        self.console.print(f"[dim]{footer}[/dim]")

        # Reset the header flag for the next response
        if hasattr(self, '_streaming_header_printed'):
            del self._streaming_header_printed

        # NOTE: We are NOT printing the full panel here for streamed responses.
        # The content is already on the screen.

    def _stop_tool_display(self):
        """Stop and clear the tool display if active."""
        if not self.verbose_mode and self.live_display:
            self.live_display.stop()
            if self.current_tool_start_time and len(self.tool_times) < len(self.tool_calls):
                elapsed = time.time() - self.current_tool_start_time
                self.tool_times.append(elapsed)
            print("\r" + " " * 120, end="\r")  # Clear line
            if self.tool_start_time:
                tool_time = time.time() - self.tool_start_time
                print(f"[dim]Tools completed in {tool_time:.2f}s total[/dim]")
            self.tool_start_time = None
            self.current_tool_start_time = None
            self.tools_running = False
            self.tool_times = []
            self.live_display = None # Ensure it's reset

    def _print_final_assistant_panel(self, content: str, response_time: float):
        """Prints the final assistant response panel with Markdown and footer."""
        assistant_panel_text = content if content else "[No Response]"
        footer = f"Response time: {response_time:.2f}s"
        print(
            Panel(
                Markdown(assistant_panel_text), 
                style="bold purple", 
                title="Assistant",
                subtitle=footer,
                expand=True
            )
        )

    async def handle_command(self, command):
        """Handle a command and update context if needed."""
        # Add a command to toggle verbose mode
        if command.lower() in ['/verbose', '/v']:
            self.verbose_mode = not self.verbose_mode
            mode_str = "verbose" if self.verbose_mode else "compact"
            print(f"[green]Switched to {mode_str} mode for tool calls.[/green]")
            return True
        
        # Add interrupt command
        if command.lower() in ['/interrupt', '/stop', '/cancel']:
            if self.tools_running:
                self.interrupt_requested = True
                print("[yellow]Interrupt requested. Waiting for current tool to complete...[/yellow]")
                return True
            else:
                print("[yellow]No tool execution in progress to interrupt.[/yellow]")
                return True
            
        # Convert context to dict for command handler
        context_dict = self.context.to_dict()
        
        # Pass to command handler
        handled = await handle_command(command, context_dict)
        
        # Update context with any changes made by commands
        self.context.update_from_dict(context_dict)
        
        return handled

    def cleanup(self):
        """Clean up resources before exiting."""
        if self.live_display:
            self.live_display.stop()