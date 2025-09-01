import logging

from openai import AsyncOpenAI

from ankibot.application.models import (
    CardGenerationRequest,
    CardGenerationResponse,
    EnglishWordRequest,
    EnglishWordResponse,
)
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

    async def generate_english_word_card(self, request: EnglishWordRequest) -> EnglishWordResponse:
        """Generate an English word card with detailed context using structured output."""
        try:
            # Create the system prompt for English word card generation
            system_prompt = self._create_english_word_system_prompt()

            # Create user message with the word
            user_message = self._create_english_word_user_message(request)

            # Call OpenAI API with structured output
            completion = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
                response_format=EnglishWordResponse,
                temperature=0.3,  # Lower temperature for more consistent definitions
                max_tokens=1500,
            )

            # Extract the structured response
            if completion.choices[0].message.parsed:
                response = completion.choices[0].message.parsed
                logger.info(f"Generated English word card for: {request.word}")
                return response
            else:
                logger.error("Failed to parse structured response from OpenAI for English word")
                # Return fallback response
                from ankibot.application.models import EnglishWordCard

                fallback_card = EnglishWordCard(
                    word=request.word,
                    definition="Failed to generate definition",
                    part_of_speech="unknown",
                    synonyms="",
                    situations_to_use="",
                    russian_translations="",
                    example_sentences="",
                )
                return EnglishWordResponse(word_card=fallback_card)

        except Exception as e:
            logger.error(f"Error generating English word card: {e}")
            # Return fallback response
            from ankibot.application.models import EnglishWordCard

            fallback_card = EnglishWordCard(
                word=request.word,
                definition="An error occurred while generating the definition",
                part_of_speech="unknown",
                synonyms="",
                situations_to_use="",
                russian_translations="",
                example_sentences="",
            )
            return EnglishWordResponse(word_card=fallback_card)

    def _create_english_word_system_prompt(self) -> str:
        """Create the system prompt for English word card generation."""
        return """You are an expert English language teacher and lexicographer specializing in creating \
comprehensive vocabulary cards for language learners.

Your task is to analyze an English word or phrase and create a detailed vocabulary card that helps \
learners understand and use the word effectively.

Guidelines for each field:

**Definition**:
- Provide a clear, concise explanation without using the word itself
- Note if the word is common/uncommon in everyday usage
- Mention typical contexts where it's used (formal, informal, academic, etc.)

**Part of Speech**:
- Provide the primary grammatical function (noun, verb, adjective, adverb, etc.)
- If multiple forms exist, choose the most common one

**Synonyms**:
- List 3-5 simpler or more common words with similar meanings
- Separate with commas
- Choose words that are easier to understand for learners

**Situations to Use It**:
- Provide 3-4 bullet points (use • symbol)
- Each point should be a brief scenario or context
- Focus on practical, real-world situations

**Russian Translations**:
- Provide 2-4 accurate Russian translations
- Separate with commas
- Include the most common and contextually appropriate translations

**Example Sentences**:
- Create exactly 5 sentences
- Each sentence should be short and easy to understand
- Follow each sentence with a brief meaning in parentheses
- Number each sentence (1. 2. 3. 4. 5.)
- Show different contexts and uses of the word

Focus on creating educational content that helps learners truly understand and remember the word."""

    def _create_english_word_user_message(self, request: EnglishWordRequest) -> str:
        """Create the user message for English word card generation."""
        return f"""Please create a comprehensive vocabulary card for the English word or phrase: "{request.word}"

Generate all the required fields with accurate, educational content that will help someone learn and \
remember this word effectively."""
