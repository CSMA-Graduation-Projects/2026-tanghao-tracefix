from pydantic import BaseModel, ConfigDict


class ExpCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    name: str
    dataset: str
    model_id: int | None = None
    sample_cnt: int = 0
    max_round: int = 3
    profile_key: str = 'full_chain'
