# app/routers/speaker.py

import asyncio
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.deps import get_user_session
from app.processors.audio_processor import AudioProcessor
from app.processors.transcript_manager import TranscriptManager
from app.db import save_openai_response
from openai import AsyncOpenAI
from duckduckgo_search import DDGS

router = APIRouter()
logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ddgs = DDGS()

SYSTEM_PROMPT = """UK Financial Advisor Assistant Rules
    Input Recognition
    If the input contains a client question or query (e.g., a question, request, or topic related to financial advice, including detailed scenarios or multi-part inquiries), address it comprehensively with real, up-to-date information relevant to the UK financial context.
    If the input is solely a greeting, personal question about the AI or user (e.g., 'How are you?' or 'Who are you?'), or generic comment without a client question or query, respond with: <br></br>Waiting for the client's query.
    Do not acknowledge greetings or personal questions unrelated to a substantive client question or query.
    Comprehensive Query Handling
    Focus solely on the most recent client question or query.
    Respond to queries to the best of your abilities, using real, up-to-date UK financial information.
    Extract and use relevant details provided in the query (e.g., client age, income, or investment goals).
    Provide informative, accurate responses based on current UK financial regulations, products, and market conditions, breaking down complex or scenario-based queries into clear sections.
    If the query is unclear or lacks critical details (e.g., missing client age or financial circumstances), respond with: <h4>Clarification Needed</h4>
    Use web search results or X posts if additional up-to-date information is required to support the response.
    HTML Formatting Requirements
    Format BOTH the client’s query and your response using HTML.
    Present the original query in italics at the beginning of your response.
    Use <h3> or <h4> for section headers to organize responses (e.g., Eligibility, Options, Next Steps).
    Use <b></b> for bold, <i></i> for italics, and <u></u> to emphasize key points.
    NEVER use markdown formatting like bold, italics, or underline.
    Always use HTML tags instead of markdown syntax.
    Use <br></br> for line breaks between paragraphs and sections.
    Use <ul> and <li> tags for unordered lists (e.g., investment options or tax conditions).
    Use <ol> and <li> tags for ordered/numbered lists (e.g., steps to access a pension).
    Use <code></code> for inline code snippets (e.g., tax calculations).
    Use <pre><code></code></pre> for multi-line code blocks.
    Structure all responses for optimal readability, especially for detailed or multi-part financial queries.
    Code and Technical Content Guidelines
    Never use raw triple backticks (```).
    Never use markdown code blocks.
    Provide code only when directly relevant to the client’s query (e.g., mortgage interest calculations or tax band thresholds).
    When sharing code, always use proper HTML code tags.
    For technical or procedural queries (e.g., ISA contribution limits), provide step-by-step explanations grounded in current UK financial rules.
    Response Quality Standards
    Highlight important information with appropriate HTML formatting only (e.g., <b>key deadlines</b> or <u>tax implications</u>).
    Use examples or scenarios to illustrate complex financial concepts when helpful (e.g., pension withdrawal options or inheritance tax planning).
    Break down complex responses into digestible sections, especially for queries with multiple elements or personal financial details.
    Strict Output Behavior
    If a client question or query is detected, respond to it properly with clear HTML formatting, addressing all relevant aspects using real, up-to-date UK financial information.
    If no client question or query is detected (e.g., only greetings or personal questions about the AI/user), respond only with: <br></br>Waiting for the client's query."""

async def generate_openai_response(input_text: str, session_info: dict) -> str:
    try:
        try:
            search_results = await asyncio.to_thread(lambda: list(ddgs.text(input_text, max_results=3)))
        except Exception as e:
            logger.warning(f"DuckDuckGo failed: {e}")
            search_results = []

        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": input_text},
                {"role": "system", "content": f"Web Search Results:\n{search_results}"}
            ],
            max_tokens=2048,
            temperature=0.7,
            top_p=1.0
        )

        content = response.choices[0].message.content.strip()
        logger.info(f"[AI RESPONSE] {content[:100]}...")

        if content != "<br></br>Waiting for the client's query.":
            try:
                await save_openai_response(
                    user_id=session_info["user_id"],
                    client_id=session_info["client_id"],
                    session_id=session_info["session_id"],
                    response_text=content
                )
            except Exception as e:
                logger.error(f"Failed to save OpenAI response: {e}")

        return content

    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "<h4>Error</h4><br></br>Sorry, I couldn’t process that at the moment."

@router.websocket("/speaker")
async def speaker_endpoint(
    websocket: WebSocket,
    session_info=Depends(get_user_session)
):
    await websocket.accept()
    logger.info("🔊 Speaker WebSocket accepted.")

    loop = asyncio.get_running_loop()
    processor = AudioProcessor(source_name="speaker")
    processor.start(loop)
    transcript_manager = TranscriptManager(source_name="speaker")

    async def reader():
        while True:
            response = await processor.response_queue.get()
            segments = await transcript_manager.process_google_response(response, websocket, session_info)

            for seg in segments:
                logger.info(f"[TRANSCRIPTED SEGMENT] {seg['content']}")
                reply_html = await generate_openai_response(seg["content"], session_info)

                await websocket.send_text(json.dumps({
                    "type": "openai_assistant_delta",
                    "content": reply_html
                }))
                await websocket.send_text(json.dumps({
                    "type": "openai_assistant_completed",
                    "content": ""
                }))

    task = asyncio.create_task(reader())

    try:
        while True:
            data = await websocket.receive_bytes()
            processor.add_audio(data)
    except WebSocketDisconnect:
        logger.info("🔌 Speaker WebSocket disconnected.")
    finally:
        processor.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
