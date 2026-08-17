from pydantic import BaseModel, Field


class User(BaseModel):
    user_id: str
    username: str


class CommentData(BaseModel):
    comment_id: str
    text: str
    from_: User = Field(alias="from")


class WebhookEvent(BaseModel):
    event_id: str
    event_type: str
    sent_at: str
    data: CommentData