"""Todo API blueprint — lightweight JSON API and standalone page for remote todo list management."""

from flask import Blueprint, request, jsonify, current_app, render_template
from refresh_task import ManualRefresh
import logging

logger = logging.getLogger(__name__)
todo_api_bp = Blueprint("todo_api", __name__)

PLUGIN_ID = "todo_list"
CONFIG_KEY = f"plugin_last_settings_{PLUGIN_ID}"

DEFAULT_SETTINGS = {
    "title": "",
    "list-title[]": [],
    "list[]": [],
    "listStyle": "disc",
    "fontSize": "normal",
}


@todo_api_bp.route('/todo')
def todo_page():
    """Serve the standalone todo list management page."""
    return render_template('todo.html')


@todo_api_bp.route('/api/todo', methods=['GET'])
def get_todo():
    """Return the current todo list settings as JSON."""
    device_config = current_app.config['DEVICE_CONFIG']
    settings = device_config.get_config(CONFIG_KEY, default=dict(DEFAULT_SETTINGS))

    # Normalize into a clean structure for the frontend
    lists = []
    titles = settings.get("list-title[]", [])
    items = settings.get("list[]", [])
    for i in range(len(titles)):
        lists.append({
            "title": titles[i] if i < len(titles) else "",
            "items": (items[i].split("\n") if i < len(items) and items[i] else []),
        })

    return jsonify({
        "title": settings.get("title", ""),
        "listStyle": settings.get("listStyle", "disc"),
        "fontSize": settings.get("fontSize", "normal"),
        "lists": lists,
    })


@todo_api_bp.route('/api/todo', methods=['POST'])
def update_todo():
    """Update the todo list and refresh the display.

    Expects JSON body:
    {
        "title": "My Tasks",
        "listStyle": "disc",
        "fontSize": "normal",
        "lists": [
            {"title": "Work", "items": ["Task 1", "Task 2"]},
            {"title": "Personal", "items": ["Task A", "Task B"]}
        ]
    }
    """
    device_config = current_app.config['DEVICE_CONFIG']
    refresh_task = current_app.config['REFRESH_TASK']

    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    lists = data.get("lists", [])
    if len(lists) > 3:
        return jsonify({"error": "Maximum 3 lists allowed"}), 400

    # Convert from the clean JSON format to the plugin's internal format
    plugin_settings = {
        "title": data.get("title", ""),
        "listStyle": data.get("listStyle", "disc"),
        "fontSize": data.get("fontSize", "normal"),
        "list-title[]": [lst.get("title", "") for lst in lists],
        "list[]": ["\n".join(lst.get("items", [])) for lst in lists],
    }

    # Persist settings
    device_config.update_value(CONFIG_KEY, plugin_settings, write=True)

    # Trigger display refresh
    if refresh_task.running:
        queued = refresh_task.queue_manual_update(ManualRefresh(PLUGIN_ID, plugin_settings))
        if queued:
            return jsonify({"success": True, "message": "Todo list updated"}), 200
        return jsonify({"error": "Could not queue refresh"}), 500

    return jsonify({"success": True, "message": "Settings saved (refresh task not running)"}), 200
