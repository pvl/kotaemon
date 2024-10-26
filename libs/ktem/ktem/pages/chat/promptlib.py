import gradio as gr
from ktem.app import BasePage
from ktem.db.models import Prompt, engine
from sqlmodel import Session, select


class PromptLibrary(BasePage):
    """Prompt selection"""

    def __init__(self, app):
        self._app = app
        self.promptlib = {}
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Accordion(label="Prompt Library", open=False) as _:
            self.prompt = gr.Dropdown(
                label="Prompts",
                choices=[""],
                value="",
                interactive=True,
                container=False,
                show_label=False,
            )

    def load_prompts(self, user_id):
        """Reload user prompt library"""

        options = []
        with Session(engine) as session:
            statement = select(Prompt).where(Prompt.user == user_id)
            results = session.exec(statement).all()
            for result in results:
                options.append((result.title, result.text))
        return dict(sorted(options))

    def reload_prompts(self, user_id):
        self.promptlib = self.load_prompts(user_id)
        choices = [""] + list(self.promptlib.keys())

        if choices:
            return gr.Dropdown(value="", choices=choices)
        else:
            return gr.Dropdown(value="", choices=[""])

    def on_prompt_selected(self, prompt_title, chat_input):
        """Handle prompt selection"""
        if prompt_title:
            return gr.Dropdown(value=""), self.promptlib.get(prompt_title, "")
        return gr.Dropdown(value=""), chat_input

    def on_subscribe_public_events(self):
        """Subscribe to the declared public event of the app"""
        self._app.subscribe_event(
            name="onPromptLibraryChanged",
            definition={
                "fn": self.reload_prompts,
                "inputs": [self._app.user_id],
                "outputs": [self.prompt],
                "show_progress": "hidden",
            },
        )

        if self._app.f_user_management:
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.reload_prompts,
                    "inputs": [self._app.user_id],
                    "outputs": [self.prompt],
                    "show_progress": "hidden",
                },
            )
            self._app.subscribe_event(
                name="onSignOut",
                definition={
                    "fn": self.reload_prompts,
                    "inputs": [self._app.user_id],
                    "outputs": [self.prompt],
                    "show_progress": "hidden",
                },
            )
