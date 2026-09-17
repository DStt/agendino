from fastapi import APIRouter, Depends

from app import depends
from controllers.RAGController import RAGController
from models.dto.MindMapRequestDTO import MindMapRequestDTO
from models.dto.RAGQueryRequestDTO import RAGQueryRequestDTO

router = APIRouter()


@router.get("/stats")
async def get_stats(
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    return rag_controller.get_stats()


@router.get("/summaries")
async def list_summaries(
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    return rag_controller.list_summaries()


@router.post("/load")
async def load_summaries(
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    return rag_controller.load_summaries()


@router.post("/search")
async def search(
    body: RAGQueryRequestDTO,
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    return rag_controller.search(body.query, body.top_k or 5, summary_ids=body.summary_ids)


@router.post("/ask")
async def ask(
    body: RAGQueryRequestDTO,
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    return rag_controller.ask(
        body.query,
        body.top_k or 5,
        summary_ids=body.summary_ids,
        provider=body.provider,
    )


@router.post("/mindmap")
async def get_mind_map(
    body: MindMapRequestDTO | None = None,
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    summary_ids = body.summary_ids if body else None
    return rag_controller.get_mind_map_data(summary_ids)


@router.post("/mindmap/generate")
async def generate_mind_map(
    body: MindMapRequestDTO | None = None,
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    summary_ids = body.summary_ids if body else None
    provider = body.provider if body else None
    return rag_controller.generate_mind_map(summary_ids, provider=provider)


@router.post("/clear")
async def clear_vector_store(
    rag_controller: RAGController = Depends(depends.get_rag_controller),
):
    return rag_controller.clear_vector_store()
