import logging

from openai import AsyncOpenAI

from ankibot.application.models import CardGenerationRequest, CardGenerationResponse
from ankibot.application.protocols import OpenAIClient

logger = logging.getLogger(__name__)


class OpenAIClientImpl(OpenAIClient):
    """Implementation of OpenAI client using structured outputs."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate_cards_from_passage(self, request: CardGenerationRequest) -> CardGenerationResponse:
        """Generate Anki cards from a text passage using structured output."""
        try:
            # Create the system prompt for card generation
            system_prompt = self._create_system_prompt(request)

            # Create user message with the passage
            user_message = self._create_user_message(request)

            # Call OpenAI API with structured output
            completion = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
                response_format=CardGenerationResponse,
                temperature=0.7,
                max_tokens=2000,
            )

            # Extract the structured response
            if completion.choices[0].message.parsed:
                response = completion.choices[0].message.parsed
                logger.info(f"Generated {len(response.cards)} cards from passage")
                return response
            else:
                logger.error("Failed to parse structured response from OpenAI")
                # Return fallback response
                return CardGenerationResponse(cards=[], summary="Failed to generate cards from the passage.")

        except Exception as e:
            logger.error(f"Error generating cards from passage: {e}")
            # Return fallback response
            return CardGenerationResponse(cards=[], summary="An error occurred while generating cards.")

    def _create_system_prompt(self, request: CardGenerationRequest) -> str:
        """Create the system prompt for card generation."""
        focus_areas_text = ""
        if request.focus_areas:
            focus_areas_text = f"\nFocus particularly on: {', '.join(request.focus_areas)}"

        return f"""You are an expert at creating high-quality Anki flashcards for effective learning and retention.

Your task is to analyze the provided text passage and generate an optimal number of Anki cards at \
{request.difficulty} difficulty level. You can create anywhere from 1 to {request.max_cards} cards, \
depending on the content richness and what would be most effective for learning.{focus_areas_text}

**Important**: Determine the appropriate number of cards based on:
- Amount of meaningful content in the passage
- Complexity of concepts presented
- Natural learning units within the text
- Avoid redundancy while ensuring comprehensive coverage

Guidelines for creating effective Anki cards:
1. **Front (Question)**: Should be clear, specific, and test understanding
2. **Back (Answer)**: Should be concise but complete, providing the key information
3. **Tags**: Use relevant keywords for organization and review
4. **Variety**: Create different types of cards (definitions, examples, applications, comparisons)
5. **Clarity**: Avoid ambiguous wording; be precise and specific
6. **Context**: Include enough context so the card makes sense independently

Difficulty levels:
- **Easy**: Basic facts, definitions, simple recall
- **Medium**: Concepts, relationships, applications
- **Hard**: Analysis, synthesis, complex reasoning

Focus on the most important and testable information from the passage. Each card should target a \
specific piece of knowledge that would be valuable for long-term retention. Create only as many \
cards as the content naturally supports - quality over quantity."""

    def _create_user_message(self, request: CardGenerationRequest) -> str:
        """Create the user message with the passage."""
        return f"""Please analyze the following passage and generate an optimal number of Anki cards \
(up to {request.max_cards} cards maximum):

---
{request.passage}
---

Create the appropriate number of cards that will help someone effectively learn and remember the key \
information from this passage. Focus on quality and natural learning units rather than hitting a \
specific number."""
