import os
import re
import ast
import subprocess
import requests
import json
from datetime import datetime

# --- File Management Tools ---
WORKSPACE = os.path.abspath("workspace")

def _secure_path(path: str):
    if os.path.isabs(path): raise ValueError("Absolute paths are not allowed.")
    full_path = os.path.abspath(os.path.join(WORKSPACE, path))
    if not full_path.startswith(WORKSPACE): raise ValueError("Path is outside the secure workspace.")
    return full_path

def create_file(path: str, content: str = ""):
    try:
        full_path = _secure_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Success: File '{path}' created."
    except Exception as e: return f"Error: {e}"

def create_folder(path: str):
    try:
        full_path = _secure_path(path)
        os.makedirs(full_path, exist_ok=True)
        return f"Success: Folder '{path}' created."
    except Exception as e: return f"Error: {e}"

def list_directory(path: str = "."):
    try:
        full_path = _secure_path(path)
        if not os.path.isdir(full_path): return f"Error: '{path}' is not a directory."
        items = os.listdir(full_path)
        return "\n".join(items) if items else f"Directory '{path}' is empty."
    except Exception as e: return f"Error: {e}"

def read_file(path: str):
    try:
        full_path = _secure_path(path)
        with open(full_path, 'r', encoding='utf-8') as f: return f.read()
    except FileNotFoundError: return f"Error: File '{path}' not found."
    except Exception as e: return f"Error: {e}"

def write_to_file(path: str, content: str, mode: str = "a"):
    if mode not in ['a', 'w']: return "Error: Invalid mode. Use 'a' for append or 'w' for write."
    try:
        full_path = _secure_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, mode, encoding='utf-8') as f: f.write(content)
        action = "appended to" if mode == "a" else "written to"
        return f"Success: Content {action} file '{path}'."
    except Exception as e: return f"Error: {e}"

# --- Code Execution Tools ---
def execute_python(code: str):
    """Execute Python code in a sandboxed environment."""
    try:
        # Create a temporary file for the code
        temp_file = os.path.join(WORKSPACE, "temp_code.py")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Execute the code
        result = subprocess.run(
            ['python3', temp_file], 
            capture_output=True, 
            text=True, 
            timeout=30,
            cwd=WORKSPACE
        )
        
        # Clean up
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        output = result.stdout
        if result.stderr:
            output += f"\nErrors:\n{result.stderr}"
        
        return output if output else "Code executed successfully with no output."
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out after 30 seconds."
    except Exception as e:
        return f"Error executing Python code: {e}"

def execute_shell(command: str):
    """Execute shell commands in the workspace."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKSPACE
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\nErrors:\n{result.stderr}"
        
        return output if output else "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        return "Error: Command execution timed out after 30 seconds."
    except Exception as e:
        return f"Error executing shell command: {e}"

# --- Web Search and Research Tools ---
def web_search(query: str, num_results: int = 5):
    """Perform a web search using a search API or service."""
    try:
        # This is a placeholder - in a real implementation, you'd use a search API
        # For now, we'll simulate a search result
        return f"Search results for '{query}':\n1. Example result 1\n2. Example result 2\n3. Example result 3"
    except Exception as e:
        return f"Error performing web search: {e}"

def fetch_url(url: str):
    """Fetch content from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return f"Content from {url}:\n{response.text[:2000]}..."
    except Exception as e:
        return f"Error fetching URL: {e}"

# --- Data Analysis Tools ---
def analyze_data(data_path: str, analysis_type: str = "summary"):
    """Analyze data from a file."""
    try:
        full_path = _secure_path(data_path)
        if not os.path.exists(full_path):
            return f"Error: File '{data_path}' not found."
        
        # Basic file analysis
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if analysis_type == "summary":
            lines = content.split('\n')
            return f"File analysis for '{data_path}':\n- Lines: {len(lines)}\n- Characters: {len(content)}\n- Words: {len(content.split())}"
        
        return f"Analysis type '{analysis_type}' not implemented yet."
    except Exception as e:
        return f"Error analyzing data: {e}"

# --- Task Management Tools ---
def create_todo(task: str, priority: str = "medium"):
    """Create a todo item."""
    try:
        todo_file = os.path.join(WORKSPACE, "tasks.json")
        
        # Load existing todos
        todos = []
        if os.path.exists(todo_file):
            with open(todo_file, 'r', encoding='utf-8') as f:
                todos = json.load(f)
        
        # Add new todo
        new_todo = {
            "id": len(todos) + 1,
            "task": task,
            "priority": priority,
            "status": "pending",
            "created": datetime.now().isoformat()
        }
        todos.append(new_todo)
        
        # Save todos
        with open(todo_file, 'w', encoding='utf-8') as f:
            json.dump(todos, f, indent=2)
        
        return f"Todo created: {task} (Priority: {priority})"
    except Exception as e:
        return f"Error creating todo: {e}"

def list_todos():
    """List all todo items."""
    try:
        todo_file = os.path.join(WORKSPACE, "tasks.json")
        
        if not os.path.exists(todo_file):
            return "No todos found."
        
        with open(todo_file, 'r', encoding='utf-8') as f:
            todos = json.load(f)
        
        if not todos:
            return "No todos found."
        
        result = "Current todos:\n"
        for todo in todos:
            status_icon = "✓" if todo["status"] == "completed" else "○"
            result += f"{status_icon} [{todo['priority'].upper()}] {todo['task']}\n"
        
        return result
    except Exception as e:
        return f"Error listing todos: {e}"

# --- Autonomous Loop Tool ---
# Registry for sub-tools available *inside* the loop
SUB_TOOL_REGISTRY = {
    "create_file": create_file,
    "create_folder": create_folder,
    "list_directory": list_directory,
    "read_file": read_file,
    "write_to_file": write_to_file,
    "execute_python": execute_python,
    "execute_shell": execute_shell,
    "web_search": web_search,
    "fetch_url": fetch_url,
    "analyze_data": analyze_data,
    "create_todo": create_todo,
    "list_todos": list_todos,
}

def autonomous_loop(initial_prompt: str, llm_caller: callable, system_prompt: str):
    """
    Executes a multi-step reasoning loop to accomplish a complex task.
    Args:
        initial_prompt: The user's original, unmodified prompt for the task.
        llm_caller: A function that can be called to communicate with the LLM.
        system_prompt: The master system prompt defining agent behavior.
    Returns:
        A list of event dictionaries detailing the agent's process.
    """
    history = [f"User task: {initial_prompt}"]
    response_events = []
    max_turns = 10  # Increased for more complex tasks

    for turn in range(max_turns):
        full_prompt = system_prompt + "\n\n**Internal Monologue History:**\n" + "\n".join(history)
        
        llm_response, model_used = llm_caller(full_prompt)
        if not llm_response:
            response_events.append({'type': 'error', 'content': 'Agent failed to respond during loop.'})
            break

        tool_match = re.search(r'<tool_code>(.*?)</tool_code>', llm_response, re.DOTALL)
        
        if tool_match:
            thought = llm_response.split('<tool_code>')[0].strip()
            if thought: 
                response_events.append({'type': 'thought', 'content': thought})
            
            tool_call_str = tool_match.group(1).strip()
            response_events.append({'type': 'tool_call', 'content': tool_call_str})
            
            try:
                func_name = tool_call_str.split('(', 1)[0]
                args_str = tool_call_str[len(func_name)+1:-1]
                args = ast.literal_eval(f"({args_str},)") if args_str else ()
                
                tool_func = SUB_TOOL_REGISTRY.get(func_name)
                if tool_func: 
                    tool_output = tool_func(*args)
                else: 
                    tool_output = f"Error: Tool '{func_name}' not found in sub-tools."
            except Exception as e:
                tool_output = f"Error executing tool: {e}"

            response_events.append({'type': 'tool_output', 'content': str(tool_output)})
            history.append(f"AI Thought: {llm_response}")
            history.append(f"Tool Output: {tool_output}")
        else:
            response_events.append({'type': 'final_answer', 'content': llm_response, 'model_used': model_used})
            break
    else:
        response_events.append({'type': 'error', 'content': 'Agent exceeded maximum turns.'})

    return response_events

# Master registry for tools callable from the main dispatcher
MASTER_TOOL_REGISTRY = {
    "autonomous_loop": autonomous_loop,
    **SUB_TOOL_REGISTRY
}

