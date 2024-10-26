import gradio as gr
import pandas as pd
from ktem.app import BasePage
from ktem.db.models import Prompt, engine
from sqlmodel import Session, select


class PromptsManagement(BasePage):

    public_events = ["onPromptLibraryChanged"]

    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Tab(label="Prompts list"):
            self.state_prompt_list = gr.State(value=None)
            self.prompt_list = gr.DataFrame(
                headers=["id", "title"],
                interactive=False,
            )

            with gr.Group(visible=False) as self._selected_panel:
                self.selected_prompt_id = gr.Number(value=-1, visible=False)
                self.title_edit = gr.Textbox(label="Title")
                self.text_edit = gr.Textbox(label="Prompt", lines=4)

            with gr.Row(visible=False) as self._selected_panel_btn:
                with gr.Column():
                    self.btn_edit_save = gr.Button("Save")
                with gr.Column():
                    self.btn_delete = gr.Button("Delete")
                    with gr.Row():
                        self.btn_delete_yes = gr.Button(
                            "Confirm delete", variant="primary", visible=False
                        )
                        self.btn_delete_no = gr.Button("Cancel", visible=False)
                with gr.Column():
                    self.btn_close = gr.Button("Close")

        with gr.Tab(label="Create prompt"):
            self.title_new = gr.Textbox(label="Title", interactive=True)
            self.text_new = gr.Textbox(label="Prompt", lines=4)
            self.btn_new = gr.Button("Save prompt")

    def on_register_events(self):
        onNewPrompt = self.btn_new.click(
            self.save_new_prompt,
            inputs=[self._app.user_id, self.title_new, self.text_new],
            outputs=[self.title_new, self.text_new],
        ).then(
            self.list_prompts,
            inputs=self._app.user_id,
            outputs=[self.state_prompt_list, self.prompt_list],
        )

        for event in self._app.get_event("onPromptLibraryChanged"):
            onNewPrompt = onNewPrompt.then(**event)

        self.prompt_list.select(
            self.select_prompt,
            inputs=self.prompt_list,
            outputs=[self.selected_prompt_id],
            show_progress="hidden",
        )
        self.selected_prompt_id.change(
            self.on_selected_prompt_change,
            inputs=[self.selected_prompt_id],
            outputs=[
                self._selected_panel,
                self._selected_panel_btn,
                # delete section
                self.btn_delete,
                self.btn_delete_yes,
                self.btn_delete_no,
                # edit section
                self.title_edit,
                self.text_edit,
            ],
            show_progress="hidden",
        )
        self.btn_delete.click(
            self.on_btn_delete_click,
            inputs=[self.selected_prompt_id],
            outputs=[self.btn_delete, self.btn_delete_yes, self.btn_delete_no],
            show_progress="hidden",
        )
        onDeletePrompt = self.btn_delete_yes.click(
            self.delete_prompt,
            inputs=[self.selected_prompt_id],
            outputs=[self.selected_prompt_id],
            show_progress="hidden",
        ).then(
            self.list_prompts,
            inputs=self._app.user_id,
            outputs=[self.state_prompt_list, self.prompt_list],
        )

        for event in self._app.get_event("onPromptLibraryChanged"):
            onDeletePrompt = onDeletePrompt.then(**event)

        self.btn_delete_no.click(
            lambda: (
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
            ),
            inputs=[],
            outputs=[self.btn_delete, self.btn_delete_yes, self.btn_delete_no],
            show_progress="hidden",
        )
        onEditPrompt = self.btn_edit_save.click(
            self.save_prompt,
            inputs=[
                self.selected_prompt_id,
                self.title_edit,
                self.text_edit,
            ],
            outputs=[self.text_edit],
            show_progress="hidden",
        ).then(
            self.list_prompts,
            inputs=self._app.user_id,
            outputs=[self.state_prompt_list, self.prompt_list],
        )

        for event in self._app.get_event("onPromptLibraryChanged"):
            onEditPrompt = onEditPrompt.then(**event)

        self.btn_close.click(
            lambda: -1,
            outputs=[self.selected_prompt_id],
        )

    def on_subscribe_public_events(self):
        self._app.subscribe_event(
            name="onSignIn",
            definition={
                "fn": self.list_prompts,
                "inputs": [self._app.user_id],
                "outputs": [self.state_prompt_list, self.prompt_list],
            },
        )
        self._app.subscribe_event(
            name="onSignOut",
            definition={
                "fn": lambda: ("", "", None, None, -1),
                "outputs": [
                    self.title_new,
                    self.text_new,
                    self.state_prompt_list,
                    self.prompt_list,
                    self.selected_prompt_id,
                ],
            },
        )

    def save_new_prompt(self, user_id, inp_title, inp_text):
        title, text = inp_title.strip(), inp_text.strip()
        if title == "":
            gr.Warning("Title cannot be empty")
            return title, text
        if len(title) > 40:
            gr.Warning("Title needs to be shorter than 40 chars")
            return title, text
        if text == "":
            gr.Warning("Prompt cannot be empty")
            return title, text

        with Session(engine) as session:
            statement = select(Prompt).where(
                Prompt.title == title, Prompt.user == user_id
            )
            result = session.exec(statement).all()
            if result:
                gr.Warning(f"A prompt already exists with given title")
                return

            prompt = Prompt(title=title, text=text, user=user_id)
            session.add(prompt)
            session.commit()
            gr.Info(f"Prompt created successfully")

        return "", "", ""

    def list_prompts(self, user_id):
        if user_id is None:
            return [], pd.DataFrame.from_records([{"id": "-", "title": "-"}])

        with Session(engine) as session:
            statement = select(Prompt).where(Prompt.user == user_id)
            results = [
                {"id": prompt.id, "title": prompt.title}
                for prompt in session.exec(statement).all()
            ]
            if results:
                prompt_list = pd.DataFrame.from_records(results)
            else:
                prompt_list = pd.DataFrame.from_records([{"id": "-", "title": "-"}])
        return results, prompt_list

    def select_prompt(self, prompt_list, ev: gr.SelectData):
        if ev.value == "-" and ev.index[0] == 0:
            gr.Info("No prompt is loaded. Please refresh the prompt list")
            return -1

        if not ev.selected:
            return -1

        return int(prompt_list["id"][ev.index[0]])

    def on_selected_prompt_change(self, selected_prompt_id):
        if selected_prompt_id == -1:
            _selected_panel = gr.update(visible=False)
            _selected_panel_btn = gr.update(visible=False)
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)
            title_edit = gr.update(value="")
            text_edit = gr.update(value="")
        else:
            _selected_panel = gr.update(visible=True)
            _selected_panel_btn = gr.update(visible=True)
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)

            with Session(engine) as session:
                statement = select(Prompt).where(Prompt.id == int(selected_prompt_id))
                prompt = session.exec(statement).one()

            title_edit = gr.update(value=prompt.title)
            text_edit = gr.update(value=prompt.text)

        return (
            _selected_panel,
            _selected_panel_btn,
            btn_delete,
            btn_delete_yes,
            btn_delete_no,
            title_edit,
            text_edit,
        )

    def on_btn_delete_click(self, selected_prompt_id):
        if selected_prompt_id is None:
            gr.Warning("No prompt is selected")
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)
            return

        btn_delete = gr.update(visible=False)
        btn_delete_yes = gr.update(visible=True)
        btn_delete_no = gr.update(visible=True)

        return btn_delete, btn_delete_yes, btn_delete_no

    def save_prompt(self, selected_prompt_id, inp_title, inp_text):
        title, text = inp_title.strip(), inp_text.strip()
        if title == "":
            gr.Warning("Title cannot be empty")
            return title, text
        if len(title) > 40:
            gr.Warning("Title needs to be shorter than 40 chars")
            return title, text
        if text == "":
            gr.Warning("Prompt cannot be empty")
            return title, text

        with Session(engine) as session:
            statement = select(Prompt).where(Prompt.id == int(selected_prompt_id))
            user = session.exec(statement).one()
            user.title = title
            user.text = text
            session.commit()
            gr.Info(f"Prompt updated successfully")

        return "", ""

    def delete_prompt(self, selected_prompt_id):
        with Session(engine) as session:
            statement = select(Prompt).where(Prompt.id == int(selected_prompt_id))
            prompt = session.exec(statement).one()
            session.delete(prompt)
            session.commit()
            gr.Info(f"Prompt deleted successfully")
        return -1
