from typing import Dict, List, Optional
from openai import AsyncOpenAI
import chainlit as cl
import chainlit.data as cl_data
from chainlit.step import StepDict
from literalai.helper import utc_now

client = AsyncOpenAI(base_url="http://localhost:8080/v1", api_key="fake_key")
cl.instrument_openai()
now = utc_now()

thread_history = [
    {
        "id": "test1",
        "name": "Pod bay doors",
        "createdAt": now,
        "userId": "test",
        "userIdentifier": "dave",
        "steps": [
            {
                "id": "test1",
                "name": "test",
                "createdAt": now,
                "type": "user_message",
                "output": "Open the pod bay doors hal",
            },
            {
                "id": "test2",
                "name": "test",
                "createdAt": now,
                "type": "assistant_message",
                "output": "I'm afraid I can't do that Dave.",
            },
        ],
    },
]  # type: List[cl_data.ThreadDict]
deleted_thread_ids = []  # type: List[str]

class TestDataLayer(cl_data.BaseDataLayer):
    async def get_user(self, identifier: str):
        return cl.PersistedUser(id="test", createdAt=now, identifier=identifier)

    async def create_user(self, user: cl.User):
        return cl.PersistedUser(id="test", createdAt=now, identifier=user.identifier)

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        thread = next((t for t in thread_history if t["id"] == thread_id), None)
        if thread:
            if name:
                thread["name"] = name
            if metadata:
                thread["metadata"] = metadata
            if tags:
                thread["tags"] = tags
        else:
            thread_history.append(
                {
                    "id": thread_id,
                    "name": name,
                    "metadata": metadata,
                    "tags": tags,
                    "createdAt": utc_now(),
                    "userId": user_id,
                    "userIdentifier": "dave",
                    "steps": [],
                }
            )

    @cl_data.queue_until_user_message()
    async def create_step(self, step_dict: StepDict):
        thread = next(
            (t for t in thread_history if t["id"] == step_dict.get("threadId")), None
        )
        if thread:
            thread["steps"].append(step_dict)

    async def get_thread_author(self, thread_id: str):
        return "dave"

    async def list_threads(
        self, pagination: cl_data.Pagination, filter: cl_data.ThreadFilter
    ) -> cl_data.PaginatedResponse[cl_data.ThreadDict]:
        return cl_data.PaginatedResponse(
            data=[t for t in thread_history if t["id"] not in deleted_thread_ids],
            pageInfo=cl_data.PageInfo(
                hasNextPage=False, startCursor=None, endCursor=None
            ),
        )

    async def get_thread(self, thread_id: str):
        return next((t for t in thread_history if t["id"] == thread_id), None)

    async def delete_thread(self, thread_id: str):
        deleted_thread_ids.append(thread_id)


cl_data._data_layer = TestDataLayer()

@cl.on_chat_start
async def main():
    await cl.Message("Hi, Dave?", disable_feedback=True).send()

@cl.on_message
async def on_message(message: cl.Message):
    response = await client.chat.completions.create(
        messages=[
            {
                "content": "You are a bot, with the personality of HAL9000",
                "role": "system"
            },
            {
                "content": message.content,
                "role": "user"
            }
        ],
        model="llama3-8b",
        temperature=0,
        max_tokens=1000

    )
    await cl.Message(content=response.choices[0].message.content).send()

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    if (username, password) == ("dave", "dave"):
        return cl.User(identifier="dave")
    else:
        return None

@cl.on_chat_resume
async def on_chat_resume(thread: cl_data.ThreadDict):
    await cl.Message(f"Welcome back to {thread['name']}").send()
    if "metadata" in thread:
        await cl.Message(thread["metadata"], author="metadata", language="json").send()
    if "tags" in thread:
        await cl.Message(thread["tags"], author="tags", language="json").send()