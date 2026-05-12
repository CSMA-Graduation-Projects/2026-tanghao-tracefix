from pydantic import BaseModel, Field, ConfigDict


class ChatSessCreate(BaseModel):
    title: str = Field(default="新会话", max_length=128)


class ChatSessUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)


class ChatMsgCreate(BaseModel):
    role: str = Field(default="user")
    msg_type: str = Field(default="text")
    content: str


class ChatToTaskIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    title: str
    lang: str = "python"
    scene: str = "func"
    dataset: str = "custom"
    problem_text: str
    model_id: int | None = None
