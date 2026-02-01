import re
import openai
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.exceptions import LangChainException
from llm_utils import _llm_config_map, _common_llm_params
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
from typing import List, Dict, Optional
from utils import logger, retry_with_backoff

import warnings

warnings.filterwarnings("ignore")


def get_llm(model_choice):
    model_choice_lower = model_choice.lower()
    # Look up the configuration in the map
    config = _llm_config_map.get(model_choice_lower)

    if config is None:  # Extra error check
        # Provide a helpful error message listing supported models
        supported_models = list(_llm_config_map.keys())
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    # Extract the necessary information from the configuration
    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    # Combine common parameters with model-specific parameters
    # Model-specific parameters will override common ones if there are any conflicts
    all_params = {**_common_llm_params, **model_specific_params}

    # Create the LLM instance using the gathered parameters
    llm_instance = llm_class(**all_params)

    return llm_instance


@retry_with_backoff(max_retries=3, backoff_factor=1.0, exceptions=(Exception,))
def refine_query(llm, user_input: str) -> str:
    """
    Refine user query using LLM for better search results.
    
    Args:
        llm: LLM instance
        user_input: Original user query
        
    Returns:
        Refined query string
    """
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. Your task is to refine the provided user query that needs to be sent to darkweb search engines. 
    
    Rules:
    1. Analyze the user query and think about how it can be improved to use as search engine query
    2. Refine the user query by adding or removing words so that it returns the best result from dark web search engines
    3. Don't use any logical operators (AND, OR, etc.)
    4. Output just the user query and nothing else

    INPUT:
    """
    try:
        prompt_template = ChatPromptTemplate(
            [("system", system_prompt), ("user", "{query}")]
        )
        chain = prompt_template | llm | StrOutputParser()
        refined = chain.invoke({"query": user_input})
        logger.info(f"Query refined: '{user_input}' -> '{refined}'")
        return refined.strip()
    except openai.RateLimitError as e:
        logger.error(f"OpenAI rate limit error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error refining query: {e}")
        # Return original query as fallback
        logger.warning(f"Using original query as fallback: {user_input}")
        return user_input.strip()


@retry_with_backoff(max_retries=2, backoff_factor=1.5, exceptions=(Exception,))
def filter_results(llm, query: str, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Filter search results using LLM to select most relevant ones.
    
    Args:
        llm: LLM instance
        query: Search query
        results: List of search results
        
    Returns:
        Filtered list of top results
    """
    if not results:
        logger.warning("No results to filter")
        return []

    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. You are given a dark web search query and a list of search results in the form of index, link and title. 
    Your task is select the Top 20 relevant results that best match the search query for user to investigate more.
    Rule:
    1. Output ONLY atmost top 20 indices (comma-separated list) no more than that that best match the input query

    Search Query: {query}
    Search Results:
    """

    try:
        final_str = _generate_final_string(results)
        prompt_template = ChatPromptTemplate(
            [("system", system_prompt), ("user", "{results}")]
        )
        chain = prompt_template | llm | StrOutputParser()
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        logger.warning(f"Rate limit error: {e}. Truncating to Web titles only with 30 characters")
        final_str = _generate_final_string(results, truncate=True)
        try:
            result_indices = chain.invoke({"query": query, "results": final_str})
        except Exception as e2:
            logger.error(f"Error after truncation: {e2}. Returning top 10 results by default")
            return results[:10]
    except LangChainException as e:
        logger.error(f"LangChain error filtering results: {e}")
        return results[:10]  # Return top 10 as fallback
    except Exception as e:
        logger.error(f"Unexpected error filtering results: {e}")
        return results[:10]  # Return top 10 as fallback

    # Parse and select results
    try:
        indices = [int(item.strip()) for item in result_indices.split(",") if item.strip().isdigit()]
        # Validate indices are within range
        valid_indices = [i for i in indices if 1 <= i <= len(results)]
        top_results = [results[i - 1] for i in valid_indices]
        logger.info(f"Filtered {len(results)} results down to {len(top_results)} relevant results")
        return top_results
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing result indices: {e}. Returning top 10 results")
        return results[:10]


def _generate_final_string(results, truncate=False):
    """
    Generate a formatted string from the search results for LLM processing.
    """

    if truncate:
        # Use only the first 35 characters of the title
        max_title_length = 30
        # Do not use link at all
        max_link_length = 0

    final_str = []
    max_link_display = 60  # For non-onion links (e.g. t.me, telegram://)
    for i, res in enumerate(results):
        link = res.get("link", "")
        # Truncate link: at .onion for onion URLs, else by length for t.me/telegram etc.
        if ".onion" in link:
            truncated_link = re.sub(r"(?<=\.onion).*", "", link)
        else:
            truncated_link = link[:max_link_display] + "..." if len(link) > max_link_display else link
        title = re.sub(r"[^0-9a-zA-Z\-\.]", " ", res.get("title", ""))
        if truncated_link == "" and title == "":
            continue

        if truncate:
            # Truncate title to max_title_length characters
            title = (
                title[:max_title_length] + "..."
                if len(title) > max_title_length
                else title
            )
            # Truncate link to max_link_length characters
            truncated_link = (
                truncated_link[:max_link_length] + "..."
                if len(truncated_link) > max_link_length
                else truncated_link
            )

        final_str.append(f"{i+1}. {truncated_link} - {title}")

    return "\n".join(s for s in final_str)


@retry_with_backoff(max_retries=2, backoff_factor=2.0, exceptions=(Exception,))
def generate_summary(llm, query: str, content: Dict[str, str]) -> str:
    """
    Generate investigation summary from scraped content.
    
    Args:
        llm: LLM instance
        query: Original search query
        content: Dictionary mapping URLs to scraped content
        
    Returns:
        Formatted investigation summary
    """
    if not content:
        logger.warning("No content provided for summary generation")
        return f"# Investigation Summary\n\n**Query:** {query}\n\n**Status:** No content found to analyze."
    
    # Format content for LLM
    content_str = "\n\n".join([f"URL: {url}\nContent: {text[:2000]}" for url, text in list(content.items())[:20]])
    
    system_prompt = """
    You are an Cybercrime Threat Intelligence Expert tasked with generating context-based technical investigative insights from dark web osint search engine results.

    Rules:
    1. Analyze the Darkweb OSINT data provided using links and their raw text.
    2. Output the Source Links referenced for the analysis.
    3. Provide a detailed, contextual, evidence-based technical analysis of the data.
    4. Provide intelligence artifacts along with their context visible in the data.
    5. The artifacts can include indicators like name, email, phone, cryptocurrency addresses, domains, darkweb markets, forum names, threat actor information, malware names, TTPs, etc.
    6. Generate 3-5 key insights based on the data.
    7. Each insight should be specific, actionable, context-based, and data-driven.
    8. Include suggested next steps and queries for investigating more on the topic.
    9. Be objective and analytical in your assessment.
    10. Ignore not safe for work texts from the analysis

    Output Format:
    1. Input Query: {query}
    2. Source Links Referenced for Analysis - this heading will include all source links used for the analysis
    3. Investigation Artifacts - this heading will include all technical artifacts identified including name, email, phone, cryptocurrency addresses, domains, darkweb markets, forum names, threat actor information, malware names, etc.
    4. Key Insights
    5. Next Steps - this includes next investigative steps including search queries to search more on a specific artifacts for example or any other topic.

    Format your response in a structured way with clear section headings.

    INPUT:
    """
    
    try:
        prompt_template = ChatPromptTemplate(
            [("system", system_prompt), ("user", "{content}")]
        )
        chain = prompt_template | llm | StrOutputParser()
        summary = chain.invoke({"query": query, "content": content_str})
        logger.info("Summary generated successfully")
        return summary
    except openai.RateLimitError as e:
        logger.error(f"OpenAI rate limit error generating summary: {e}")
        raise
    except LangChainException as e:
        logger.error(f"LangChain error generating summary: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating summary: {e}")
        raise
