"""Task definitions and queue management for browser development."""

from orchestrator.state import StateManager

# Browser component task definitions
BROWSER_TASKS = [
    {
        "name": "Setup project structure",
        "component": "core",
        "description": """Create the basic browser project structure in the browser/ directory:
- browser/main.py - Entry point
- browser/window.py - Main window class using PyQt6
- browser/config.py - Browser configuration

The main window should:
1. Create a QMainWindow with title "MyBrowser"
2. Set minimum size to 1024x768
3. Have a central widget placeholder
4. Be runnable with: python browser/main.py

Use PyQt6 for the GUI. Keep it minimal but functional.""",
        "dependencies": []
    },
    {
        "name": "Implement URL bar",
        "component": "ui",
        "description": """Add a URL bar to the browser window:
- browser/components/url_bar.py - URL input widget

Features:
1. QLineEdit for URL input
2. Go button to trigger navigation
3. Enter key triggers navigation
4. Signal emitted when URL is submitted: url_submitted(str)

Integrate into main window at the top.""",
        "dependencies": [1]  # Depends on project structure
    },
    {
        "name": "Implement tab manager",
        "component": "ui",
        "description": """Add tabbed browsing support:
- browser/components/tab_manager.py - Tab management widget

Features:
1. QTabWidget to hold multiple tabs
2. New tab button (+)
3. Close tab button (x) on each tab
4. Tab shows page title
5. Signals: new_tab_requested(), tab_closed(int), tab_changed(int)

Integrate into main window as central widget.""",
        "dependencies": [1]
    },
    {
        "name": "Implement HTTP networking",
        "component": "networking",
        "description": """Create the networking layer:
- browser/networking/http_client.py - HTTP/HTTPS client

Features:
1. Async HTTP GET requests using urllib or httpx
2. Support for HTTPS
3. Follow redirects (max 10)
4. Timeout handling (30 seconds)
5. Return response with: status_code, headers, body, final_url
6. Handle common errors gracefully

Keep it simple - no connection pooling needed yet.""",
        "dependencies": [1]
    },
    {
        "name": "Implement HTML parser",
        "component": "parser",
        "description": """Create a basic HTML parser:
- browser/parser/html_parser.py - HTML tokenizer and DOM builder
- browser/parser/dom.py - DOM node classes

Features:
1. Parse HTML string into DOM tree
2. Handle common tags: html, head, body, div, span, p, a, img, h1-h6, ul, ol, li
3. Extract text content
4. Extract links (href from <a> tags)
5. Handle malformed HTML gracefully (don't crash)

Use Python's html.parser as a base, build DOM tree on top.""",
        "dependencies": [1]
    },
    {
        "name": "Implement basic CSS parser",
        "component": "parser",
        "description": """Create a basic CSS parser:
- browser/parser/css_parser.py - CSS tokenizer and rule parser

Features:
1. Parse inline styles and <style> blocks
2. Support basic selectors: element, .class, #id
3. Parse common properties: color, background-color, font-size, margin, padding, display
4. Return structured style rules

Keep it simple - no cascade calculation yet.""",
        "dependencies": [1]
    },
    {
        "name": "Implement content view",
        "component": "rendering",
        "description": """Create a content display widget:
- browser/components/content_view.py - Renders page content

Features:
1. QWidget that displays parsed HTML
2. Use QTextBrowser or custom painting for basic rendering
3. Display text content with basic formatting
4. Make links clickable (emit signal with URL)
5. Show images (basic support)
6. Signal: link_clicked(str)

This is a simplified renderer - not pixel-perfect.""",
        "dependencies": [5, 6]  # Depends on HTML and CSS parsers
    },
    {
        "name": "Implement page loader",
        "component": "core",
        "description": """Create the page loading coordinator:
- browser/core/page_loader.py - Coordinates fetching and parsing

Features:
1. Takes a URL, fetches content via HTTP client
2. Parses HTML response
3. Extracts and applies CSS
4. Returns parsed page object ready for rendering
5. Handle errors (network, parse) gracefully
6. Async operation with progress/status signals

Wire together: networking -> parsing -> ready for display.""",
        "dependencies": [4, 5, 6]  # Depends on networking, HTML parser, CSS parser
    },
    {
        "name": "Implement navigation controller",
        "component": "core",
        "description": """Create navigation logic:
- browser/core/navigation.py - History and navigation controller

Features:
1. Navigate to URL (triggers page load)
2. Back/Forward history
3. History stack per tab
4. Current URL tracking
5. Signals: navigation_started(str), navigation_complete(str), navigation_failed(str, error)

Integrate with tab manager - each tab has its own history.""",
        "dependencies": [3, 8]  # Depends on tab manager, page loader
    },
    {
        "name": "Integration and wiring",
        "component": "integration",
        "description": """Wire all components together in main.py:

1. URL bar submit -> navigation controller -> page loader -> content view
2. Tab switching updates URL bar and content view
3. Link clicks in content view -> navigation controller
4. Back/Forward buttons work
5. New tab opens with blank page or home page
6. Window title shows current page title

Test the full flow:
- Run browser: python browser/main.py
- Enter URL in bar
- Page loads and displays
- Links are clickable
- Tabs work
- Back/Forward work

Fix any integration bugs.""",
        "dependencies": [2, 3, 7, 9]  # Depends on URL bar, tabs, content view, navigation
    }
]


def initialize_tasks(state: StateManager):
    """Load all browser tasks into the database if not already present."""
    existing = state.get_all_tasks()
    if existing:
        return  # Tasks already loaded

    for task_def in BROWSER_TASKS:
        state.create_task(
            name=task_def["name"],
            component=task_def["component"],
            description=task_def["description"],
            dependencies=task_def["dependencies"]
        )
    state.log("tasks_initialized", f"Created {len(BROWSER_TASKS)} tasks")
