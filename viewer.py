import argparse
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Grid
from textual.widgets import (Input,
                             DataTable,
                             Button,
                             TextArea,
                             Static,
                             Label,
                             Footer,
                             Checkbox,
                             RadioSet,
                             RadioButton,
                             Select,
                             )
from textual.screen import Screen
from textual.reactive import reactive
from textual.widgets import Input
from textual.message import Message
import json
from datetime import datetime
import logging
from textual.logging import TextualHandler
from collections import defaultdict

# logging.basicConfig(
#     level="NOTSET",
#     handlers=[TextualHandler()],
# )

logging.basicConfig(
    filename="app.log",         # Path to your log file
    level=logging.DEBUG,        # Minimum level to log (DEBUG, INFO, WARNING, etc.)
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

MAX_LINES = 0  # Maximum number of lines to read from the JSONL file


# --------- CLI Argument Parsing ---------
parser = argparse.ArgumentParser(description="Inspect IPython JSONL log")
parser.add_argument("logfile", help="Path to JSON Lines log file")
#parser.add_argument("--before", type=str, help="Only show entries before this ISO timestamp")
#parser.add_argument("--after", type=str, help="Only show entries after this ISO timestamp")
#parser.add_argument("--contains", type=str, help="Only show entries where command contains this string")
args = parser.parse_args()


options = [
    RadioButton("1h", id="last_1h"),
    RadioButton("6h", id="last_6h"),
    RadioButton("24h", id="last_24h"),
    RadioButton("7d", id="last_7d"),
    RadioButton("30d", id="last_30d"),
    RadioButton("all", id="all"),
    RadioButton("custom", id="custom"),
]


class Options(Screen):
    def __init__(self, current_settings: dict[str, str | bool] | None = None) -> None:
        super().__init__()
        self.current_settings = current_settings or {}

    def compose(self) -> ComposeResult:
        yield Static("Options screen - coming soon!")
        yield Button("Back to main screen", id="back_button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()  # Close this screen


class ScreenResult(Message):
    def __init__(self, sender, data: dict):
        super().__init__()
        self.sender = sender
        self.data = data


class GridFormScreen(Screen):
    CSS = """
    Screen {
        layout: vertical;
        padding: 1;
    }

    #screen-title {
        text-style: bold;
        content-align: center middle;
        padding: 1;
        color: cyan;
    }

    .section-title {
        text-style: bold;
        padding: 0 0;
        color: yellow;
    }

    .field-label {
        text-style: italic;
        color: white;
        margin-bottom: 0;
    }

    .field-group {
        padding: 1 0;
    }

    .form-section {
        padding: 1;
        border: tall dimgray;
    }

    .grid-form {
        padding: 2;
        layout: vertical;
        height: 100%;
    }

    #back_button {
        width: 20;
        height: 3;
        dock: bottom;
    }

    .horizontal-radio {
        layout: horizontal;
        text-wrap: wrap;
    }

    .radio-option-disabled {
        color: gray;
        text-style: dim;
        opacity: 0.5;
    }

    .radio-option-disabled RadioButton {
        color: gray;
    }
    """
    def __init__(self, definition: dict, current_state: dict | None = None) -> None:
        super().__init__()
        self.definition = definition
        self.current_state = current_state or {}
        try:
            self.title = self.definition['title']
        except:
            self.title = None

    def create_widget_from_field(self, field: dict, value: str | bool | None = None):
        fid = field["name"]
        ftype = field["type"]

        match ftype:
            case "text":
                return Input(value=str(value or ""), id=fid)

            case "checkbox":
                return Checkbox(value=bool(value), id=fid)

            case "select":
                options = [(opt, opt) if isinstance(opt, str) else (opt["label"], opt["value"]) for opt in field["options"]]
                return Select(options, value=value, id=fid)

            case "radio":
                buttons = []
                for opt in field["options"]:
                    if isinstance(opt, str):
                        label = opt
                        val = opt
                        disabled = False
                    else:
                        label = opt.get("label", opt.get("value", ""))
                        val = opt["value"]
                        disabled = opt.get("disabled", False)

                    rb = RadioButton(label,
                                     value=val,
                                     id=f"{fid}-{val}",
                                     disabled=disabled,
                                     classes="radio-option-disabled" if disabled else "")
                    buttons.append(rb)
                radio_set = RadioSet(*buttons, id=fid, classes="horizontal-radio")
                radio_set.value = value
                return radio_set
            
            case _:
                raise ValueError(f"Unsupported field type: {ftype}")

    def compose(self) -> ComposeResult:
        # Top-level layout
        layout = []

        # Screen title (styleable via `.screen-title`)
        if self.title:
            layout.append(Label(self.title, id="screen-title", classes="screen-title"))

        # Sections
        for section in self.definition.get("sections", []):
            section_widgets = []

            # Section title (styleable via `.section-title`)
            if "title" in section:
                section_widgets.append(Label(section["title"], classes="section-title"))

            # Fields
            for field in section.get("fields", []):
                fid = field["name"]
                value = field.get("value", self.current_state.get(fid))

                label = Label(field["label"], classes="field-label")

                widget = self.create_widget_from_field(field, value)

                # Wrap label + widget in a container (styleable via `.field-group`)
                field_group = Vertical(
                    label,
                    widget,
                    id=f"{fid}-group",
                    classes="field-group",
                )
                section_widgets.append(field_group)

            # Wrap section in a container (styleable via `.form-section`)
            layout.append(Vertical(*section_widgets, classes="form-section"))

        # Compose all into the screen
        yield Vertical(*layout, id="form-container", classes="grid-form")
        yield Button("Back to main screen", id="back_button")



    # def on_button_pressed(self, event: Button.Pressed) -> None:
    #     if event.button.id == "back_button":
    #         self.app.pop_screen()  # Close this screen

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back_button":
            result = {}
            for section in self.definition.get("sections", []):
                for field in section.get("fields", []):
                    fid = field["name"]
                    wid = self.query_one(f"#{fid}")
                    if field["type"] == "text":
                        result[fid] = wid.value
                    elif field["type"] == "checkbox":
                        result[fid] = wid.value
                    elif field["type"] == "select":
                        result[fid] = wid.value
                    elif field["type"] == "radio":
                        result[fid] = wid.value
            self.post_message(ScreenResult(self, result))
            self.app.pop_screen()
            
        elif event.button.id == "cancel":  # If you have a cancel button
            self.app.pop_screen()


class JsonlInspectorApp(App):
    CSS = """
    Screen {
        layout: vertical;
        padding: 1;
    }
    #search_input {
        height: 3;
    }
    #table {
        height: 30;
    }
    #details {
        height: 15;
    }
    #options_bar {
        height: 3;
        width: 20;
        dock: bottom;
    }
    #time_filter_set {
        height: 3;
        layout: horizontal;
    }
    #time_filter_range_container {
        height: 3;
        layout: horizontal;
    }
    #footer {
        height: 1;
        dock: bottom;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit")
    ]

    jsonl_path = args.logfile# "/home/hegedues/prog/nats/history_converted.jsonl"

    highlight_ascan = reactive(False)
    form_definition = None

    # read the form definition from a JSON file
    with open("settings.json") as f:
        form_definition = json.load(f)
    # define the initial data for the form
    def extract_defaults_from_form_definition(definition: dict) -> dict:
        result = {}
        for section in definition.get("sections", []):
            for field in section.get("fields", []):
                name = field["name"]
                default = field.get("default")
                # Optional fallback logic (e.g. use first option if no default given)
                if default is None and field["type"] in ("select", "radio"):
                    options = field.get("options", [])
                    if options:
                        first = options[0]
                        default = first["value"] if isinstance(first, dict) else first
                result[name] = default
        return result

    current_settings = reactive(extract_defaults_from_form_definition(form_definition))

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Input(placeholder="Command field live search...", id="search_input"),
            Checkbox("Highlight only", id="live_search_highlight", value=False), # this is to be able to highlight the search results in the table
        )
        yield DataTable(id="table", zebra_stripes=True, cursor_type="row")
        yield TextArea(id="details", read_only=True, show_line_numbers=True)
        yield Horizontal(
            Checkbox("Highlight isses", id="highlight_issues", value=False),
            Checkbox("Highlight 'ascan' commands", id="highlight_ascan", value=False),
            Checkbox("Show issues only", id="show_issues_only", value=False),
        )

        yield Horizontal(
            Button("Show options", id="options_btn"),
            id="options_bar"
        )
        yield RadioSet(
            RadioButton("1h", id="last_1h"),
            RadioButton("6h", id="last_6h"),
            RadioButton("24h", id="last_24h"),
            RadioButton("7d", id="last_7d"),
            RadioButton("30d", id="last_30d"),
            RadioButton("all", id="all"),
            RadioButton("custom", id="custom"),
            id="time_filter_set",
        )
        yield Horizontal(
            Static("Time range:", id="time_range_label"),
            Input(placeholder="YYYY-MM-DD HH:MM:SS", id="custom_start", value=""),
            Input(placeholder="YYYY-MM-DD HH:MM:SS", id="custom_end", value=""),
            id="time_filter_range_container",
        )
        yield Footer(
            Static("Press 'q' to quit", id="footer_text"),
            id="footer"
        )

    def on_mount(self):
        self.time_filter_set = self.query_one("#time_filter_set", RadioSet)
        self.time_filter_set.display = False  # Hide by default
        self.time_filter_range_container = self.query_one("#time_filter_range_container", Horizontal)
        self.time_filter_range_container.display = False
        self.highlight_ascan_checkbox = self.query_one("#highlight_ascan", Checkbox)
        self.highlight_issues_checkbox = self.query_one("#highlight_issues", Checkbox)
        self.show_issues_only_checkbox = self.query_one("#show_issues_only", Checkbox)
        self.search_input = self.query_one("#search_input", Input)
        self.live_search_highlight = self.query_one("#live_search_highlight", Checkbox)
        self.table = self.query_one("#table", DataTable)
        self.details = self.query_one("#details", TextArea)
        #self.footer_text = self.query_one("#footer_text", Static)
        self.options_bar = self.query_one("#options_bar", Horizontal)

        self.data = self.load_jsonl()
        self.strip_commands()  # this will clean up the command strings, inplace
        self.highlight_issues = False
        self.highlight_ascan = False
        self.reverse_sort = False
        self.filtered_data = self.data.copy()
        self.column_headers = ["#", "line", "spock", "start_time", "duration", "command"]
        self.sorted_column_headers = self.column_headers.copy()
        self.build_table(self.filtered_data)
        self.set_focus(self.table)

    def load_jsonl(self):
        path = os.path.expanduser(self.jsonl_path)
        try:
            with open(path, "r") as f:
                lines = f.readlines()[-MAX_LINES:]
                return [json.loads(line) for line in lines if line.strip()]
        except Exception as e:
            self.console.print(f"Error loading log: {e}")
            return []

    def strip_commands(self):
        for entry in self.data:
            command = entry.get("command", "")
            if command.startswith("get_ipython().run_line_magic"):
                # Remove the magic command wrapper
                command = command.replace("get_ipython().run_line_magic", "")\
                    .strip("()")\
                    .replace("\'", "")\
                    .replace("\"", "")\
                    .replace(", ", " ")\
                    .replace("%", "")
            entry["command"] = command
            profile = entry.get("profile", "")
            if profile == 'spockdoor':
                profile = '1'
            elif profile == 'secondDoor':
                profile = '2'
            elif profile == 'thirdDoor':
                profile = '3'
            entry["profile"] = profile

    def issue_filter(self, entry: dict) -> bool:
        """
        Filter function to determine if an entry is an issue.
        This can be customized based on the criteria for issues.
        """
        if 'www' in entry.get("command", ""):
            return True
        if 'error' in entry.get("stdout", "") or 'Error' in entry.get("stdout", ""):
            return True
        if 'DevError' in entry.get("stdout", ""):
            return True
    
    def issues_only_filter(self,) -> None:
        self.filtered_data = [e for e in self.data if self.issue_filter(e)]
        self.build_table(self.filtered_data)


    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "highlight_ascan":
            self.highlight_ascan = event.checkbox.value
        elif event.checkbox.id == "highlight_issues":
            self.highlight_issues = event.checkbox.value
        elif event.checkbox.id == "show_issues_only":
            self.issues_only_filter()
        self.build_table(self.filtered_data)

    async def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """
        Handle header selection in the DataTable.
        This can be used to sort or filter data based on the selected column.
        """
        col_name = str(event.label)
        if col_name.endswith(" ↑") or col_name.endswith(" ↓"):
            # If the column is already sorted, toggle the sort direction
            col_name = col_name[:-2]
        logging.debug(f"Header selected: {col_name}")
        if col_name in ["#", 'spock']:
            return None

        #reverse = getattr(self, "reverse_sort", False)
        self.reverse_sort = not self.reverse_sort
        logging.debug(f"{self.reverse_sort=}")

        def cast(val, col_name=col_name):
            if col_name in ("line", "start_time", "duration"):
                # Attempt to convert to float for numerical sorting
                try:
                    return float(val)
                except ValueError:
                    return val
            if col_name == "command":
                # For command, we keep it as a string
                return val

        self.sorted_data = sorted(
            self.filtered_data,
            key=lambda row: cast(row[col_name]),
            reverse=self.reverse_sort
        )

        # update the header style to indicate sorting
        arrow = " ↓" if self.reverse_sort else " ↑"
        self.sorted_column_headers = []
        for coln in self.column_headers:
            if coln != str(col_name):
                self.sorted_column_headers.append(coln)
                #logging.debug(f"Column {col_name} not sorted, keeping original order")
            elif coln == str(col_name):
                self.sorted_column_headers.append(coln + arrow)
                logging.debug(f"Column {coln} sorted, adding arrow: {arrow}")

        logging.debug(f"Sorted column headers: {self.sorted_column_headers}")

        self.build_table(self.sorted_data)
        logging.debug(f"Data sorted by <{str(event.label)}> in {'descending' if self.reverse_sort else 'ascending'} order")




    def build_table(self, data: list[dict] | None = None) -> None:
        current_scroll = self.table.scroll_y
        focused_row = self.table.cursor_row

        self.table.clear(columns=True)
        self.table.add_columns(*self.sorted_column_headers)
        self.table.column_labels = self.sorted_column_headers  # this can be used to set the column labels, but keep column names internally
        for i, entry in enumerate(data):
            
            if self.highlight_issues and self.issue_filter(entry):
                styled_row = [
                    str(i + 1),
                    str(entry.get("line", "")),
                    entry.get("profile", ""),
                    entry.get("start_time", "").partition(".")[0],  # Remove milliseconds,
                    entry.get("duration", ""),
                    Text(str(entry.get("command", "")[:80]), style="bold red"),
                    ]
            elif self.highlight_ascan and 'ct' in entry.get("command", ""):
                styled_row = [
                    str(i + 1),
                    str(entry.get("line", "")),
                    entry.get("profile", ""),
                    entry.get("start_time", "").partition(".")[0],  # Remove milliseconds,
                    entry.get("duration", ""),
                    Text(str(entry.get("command", "")[:80]), style="bold green"),
                    ]
            else:
                styled_row = [
                    str(i + 1),
                    str(entry.get("line", "")),
                    entry.get("profile", ""),
                    entry.get("start_time", "").partition(".")[0],  # Remove milliseconds
                    entry.get("duration", ""),
                    entry.get("command", "")[:80]]
            self.table.add_row(*styled_row)
        try:
            self.table.scroll_y = current_scroll  # Restore scroll position
            self.table.focused_raw = (focused_row)
        except:
            pass
            # self.table.add_row(
            #     str(entry.get("line", "")),
            #     entry.get("start_time", ""),
            #     entry.get("command", "")[:80]
            # )

#    def update_table(self):
#        for i, entry in enumerate(self.filtered_data):


    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        self.filtered_data = [
            e for e in self.data if query in e.get("command", "").lower()
        ]
        self.build_table(self.filtered_data)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        #logging.debug(f"Row selected: {event.row_key}")
        row_index = self.table.get_row_index(event.row_key)
        if row_index is not None and 0 <= row_index < len(self.filtered_data):
            entry = self.filtered_data[row_index]
            details = ["Command:", entry.get("command", "")]
            if entry.get("stdout"):
                details.append("\nStdout:")
                details.append(entry.get("stdout", ""))
            if entry.get("result"):
                details.append("\nResult:")
                details.append(entry.get("result", ""))
            if entry.get("error"):
                details.append("\nError:")
                details.append(entry.get("error", ""))
            self.details.text = "\n".join(details)
            # self.details.text = (
            #     f"Command:\n{entry['command']}\n\n"
            #     f"Stdout:\n{entry['stdout']}\n\n"
            #     f"Result:\n{entry['result']}\n\n"
            #     f"Error:\n{entry['error']}"
            # )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "options_btn":
            self.push_screen(GridFormScreen(self.form_definition,
                                            current_state=self.current_settings))
    
    def on_screen_result(self, message: ScreenResult):
        logging.info("Received form result:", message.data)
        self.current_settings = message.data
        


if __name__ == "__main__":
    import os
    JsonlInspectorApp().run()
